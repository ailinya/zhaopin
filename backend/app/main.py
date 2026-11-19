"""
FastAPI 应用入口
@author: 星浩AI
@description: AI 驱动的智能面试系统后端 API

包含：
- FastAPI app 工厂
- lifespan 启动/关闭
- CORS 中间件
- 全局异常 handler（§16.2 借鉴 GraphRAGAgent 模式）
- 健康检查端点
- 路由注册（Week 1 Day 4 开始接入）
"""
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import settings
from app.core.errors import APIError, ErrorCode
from app.core.logging import configure_logging, get_logger
from app.core.main_loop import set_main_loop
from app.database import init_db
from app.schemas.response import APIResponse


# ===== 日志 =====
configure_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


# ===== Lifespan（启动/关闭）=====
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # ===== 启动阶段 =====
    logger.info("application_starting", version=__version__, env=os.getenv("ENV", "development"))

    # 1. 保存全局 event loop 引用（§4 行动项 #1，§10.6 后台线程推送 SSE 用）
    set_main_loop(asyncio.get_running_loop())
    logger.info("main_loop_registered")

    # 2. 初始化数据库（Week 2 才有实际模型）
    try:
        init_db()
        logger.info("database_initialized")

        # 3. 创建默认用户（如果不存在）
        from app.database import SessionLocal
        from app.models import User
        from app.core.security import hash_password

        db = SessionLocal()
        try:
            existing_user = db.query(User).filter(User.username == "admin").first()
            if not existing_user:
                default_user = User(
                    id="user-default-admin",
                    username="admin",
                    email="admin@company.com",
                    password_hash=hash_password("123456"),
                    full_name="Admin",
                    is_admin=True,
                )
                db.add(default_user)
                db.commit()
                logger.info("default_user_created", username="admin")
        finally:
            db.close()
    except Exception as e:
        logger.warning("database_init_skipped", reason=str(e))

    # 4. 确保存储目录存在
    storage_path = Path(settings.STORAGE_PATH)
    storage_path.mkdir(parents=True, exist_ok=True)
    for subdir in ["resumes", "audio", "reports", "logs"]:
        (storage_path / subdir).mkdir(exist_ok=True)
    logger.info("storage_ready", path=str(storage_path))

    # 5. Whisper 模型 eager-load（§13.3）
    #    失败不阻塞应用启动（lazy load fallback）
    try:
        # 5a. 先确保 ffmpeg 在 PATH 里（whisper.transcribe 用 subprocess 调 ffmpeg）
        from app.core.ffmpeg import ensure_ffmpeg_in_path
        ffmpeg_path = ensure_ffmpeg_in_path()
        if ffmpeg_path:
            logger.info("ffmpeg_ready", extra={"ffmpeg_path": ffmpeg_path})
        else:
            logger.warning("ffmpeg_missing", extra={"hint": "请安装 ffmpeg 并加到 PATH，否则 webm 录音无法转写"})

        # 5b. 加载 Whisper 模型
        from app.services.asr_service import load_whisper_model
        loop = asyncio.get_running_loop()  # asyncio 已在模块顶部 import
        await loop.run_in_executor(None, load_whisper_model)
    except Exception as e:
        logger.warning("whisper_load_skipped", reason=str(e))

    # 6. APScheduler（卡住巡检）
    try:
        from app.workers.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning("scheduler_start_skipped", reason=str(e))

    logger.info("application_started")

    yield  # 应用运行中

    # ===== 关闭阶段 =====
    logger.info("application_shutting_down")
    try:
        from app.workers.scheduler import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.warning("scheduler_stop_failed", reason=str(e))
    try:
        from app.services.asr_service import release_whisper_model
        release_whisper_model()
    except Exception as e:
        logger.warning("whisper_release_failed", reason=str(e))
    logger.info("application_stopped")


# ===== FastAPI App =====
app = FastAPI(
    title="星浩AI - 智能面试系统 API",
    description="星浩AI驱动的自动化面试系统后端 API | 公众号：星浩AI",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ===== CORS 中间件 =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== 全局异常 handler（§16.2 借鉴模式）=====
@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """业务异常 → 统一响应格式"""
    logger.warning(
        "api_error",
        code=exc.detail.get("code"),
        msg=exc.detail.get("msg"),
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse.err(
            code=exc.detail.get("code", ErrorCode.INTERNAL_ERROR),
            msg=exc.detail.get("msg", "未知错误"),
            data=exc.detail.get("data"),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未捕获异常 → 统一响应格式"""
    logger.error(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        exc_msg=str(exc),
        path=request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=APIResponse.err(
            code=ErrorCode.INTERNAL_ERROR,
            msg="服务器内部错误",
        ).model_dump(),
    )


# ===== 路由注册（Week 1 Day 4+ 接入）=====
from app.api.router import api_router

app.include_router(api_router)


# ===== 健康检查 =====
@app.get("/healthz", tags=["system"])
async def healthz() -> APIResponse[dict]:
    """存活检查（liveness probe）"""
    return APIResponse.ok({"status": "ok", "version": __version__})


@app.get("/readyz", tags=["system"])
async def readyz() -> APIResponse[dict]:
    """就绪检查（readiness probe）"""
    checks = {
        "db": _check_db(),
        "storage": _check_storage(),
        "disk_space": _check_disk_space(),
    }
    all_ok = all(c["ok"] for c in checks.values())
    return APIResponse.ok(
        {
            "ready": all_ok,
            "checks": checks,
        }
    )


def _check_db() -> dict:
    """检查数据库连接"""
    try:
        from app.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _check_storage() -> dict:
    """检查存储目录"""
    try:
        storage_path = Path(settings.STORAGE_PATH)
        return {"ok": storage_path.exists(), "path": str(storage_path)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _check_disk_space() -> dict:
    """检查磁盘空间（> 1GB）"""
    try:
        import shutil
        storage_path = Path(settings.STORAGE_PATH)
        stat = shutil.disk_usage(storage_path)
        free_gb = stat.free / (1024 ** 3)
        return {"ok": free_gb > 1, "free_gb": round(free_gb, 2)}
    except Exception as e:
        return {"ok": False, "error": str(e)}