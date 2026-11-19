"""
Candidates API（§12 + §11）

端点（HR 端，JWT 鉴权）：
- GET    /api/candidates              列表
- POST   /api/candidates              上传（含 multipart/form-data）
- GET    /api/candidates/{id}         详情
- GET    /api/candidates/{id}/resume  下载简历
- DELETE /api/candidates/{id}         删除（级联）
"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.errors import APIError, ErrorCode
from app.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.candidate import (
    CandidateOut,
    CandidateListResponse,
    CandidateCreateResponse,
    ResumeTextResponse,
)
from app.schemas.response import APIResponse
from app.services.candidate_service import CandidateService


router = APIRouter(prefix="/api/candidates", tags=["candidates"])


# 简历文件 magic bytes
PDF_MAGIC = b"%PDF-"
DOCX_MAGIC = b"PK\x03\x04"  # ZIP (docx 是 zip)


@router.get("", response_model=APIResponse[CandidateListResponse])
async def list_candidates(
    position_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取候选人列表"""
    service = CandidateService(db, actor_id=user.id)
    skip = (page - 1) * page_size
    items, total = service.list_candidates(position_id=position_id, skip=skip, limit=page_size)
    return APIResponse.ok(
        CandidateListResponse(
            items=[CandidateOut.model_validate(c) for c in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", response_model=APIResponse[CandidateCreateResponse], status_code=201)
async def create_candidate(
    name: str = Form(..., min_length=1),
    email: str = Form(..., min_length=3),
    position_id: int = Form(..., ge=1),
    resume: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传候选人简历（multipart/form-data）"""
    # 读取文件前 8 字节（用于 magic bytes 检测）
    header = await resume.read(8)
    content_bytes = header + await resume.read()

    # 文件类型检测（§11.2）
    if header[:5] == PDF_MAGIC:
        resume_type = 0
    elif header[:4] == DOCX_MAGIC:
        resume_type = 1
    else:
        raise APIError.bad_request(
            ErrorCode.UNSUPPORTED_FILE_TYPE,
            "不支持的文件类型，仅接受 PDF/DOCX",
        )

    # 文件大小（50MB）
    if len(content_bytes) > 50 * 1024 * 1024:
        raise APIError.bad_request(
            ErrorCode.FILE_TOO_LARGE,
            "文件过大，最大 50MB",
        )

    # 创建候选人（PDF BLOB 直接入 DB，Week 2 切文件）
    service = CandidateService(db, actor_id=user.id)
    candidate = service.create_candidate(
        position_id=position_id,
        name=name,
        email=email,
        resume_type=resume_type,
        resume_content=content_bytes,
        uploaded_by=user.id,
    )

    # Week 2: 后台线程触发简历解析（§11.3）
    _schedule_parse(
        candidate_id=candidate.id,
        resume_content=content_bytes,
        resume_type=resume_type,
        trigger="upload",
    )

    return APIResponse.ok(
        CandidateCreateResponse(
            candidate_id=candidate.id,
            parse_status="parsing",
        )
    )


def _schedule_parse(
    candidate_id: str,
    resume_content: bytes,
    resume_type: int,
    trigger: str = "upload",
) -> None:
    """调度后台线程：解析简历 → 写 DB → 推 SSE

    Args:
        trigger: 触发来源，"upload" | "reparse"。影响 audit log event_type 与 SSE payload。
    """
    import asyncio
    import logging
    from app.services.resume_parser_service import (
        ResumeParseError, parse_pdf_bytes, parse_docx_bytes,
    )
    from app.services.sse_manager import get_sse_manager
    from app.models import CandidateRepository, AuditLogRepository
    from app.database import SessionLocal
    from app.core.main_loop import get_main_loop

    logger = logging.getLogger(__name__)

    async def _do_parse_and_update():
        sse = get_sse_manager()

        # 1. 推 started 事件
        await sse.publish(candidate_id, {
            "event": "resume_parse_started",
            "data": {"candidate_id": candidate_id, "trigger": trigger},
        })

        # 2. 解析（同步阻塞，在 executor 里跑）
        from functools import partial
        loop = get_main_loop()
        try:
            if resume_type == 0:
                parse_func = partial(parse_pdf_bytes, resume_content)
            else:
                parse_func = partial(parse_docx_bytes, resume_content)
            text = await loop.run_in_executor(None, parse_func)
        except ResumeParseError as e:
            # 解析失败：写 DB + 推 SSE failed
            _update_candidate_status(
                candidate_id, parse_status=3, parse_error=f"{e.code}: {e.message}",
            )
            await sse.publish(candidate_id, {
                "event": "resume_parse_failed",
                "data": {
                    "candidate_id": candidate_id,
                    "error_code": e.code,
                    "error_message": e.message,
                    "trigger": trigger,
                },
            })
            return
        except Exception as e:
            _update_candidate_status(
                candidate_id, parse_status=3, parse_error=f"UNEXPECTED: {e}",
            )
            await sse.publish(candidate_id, {
                "event": "resume_parse_failed",
                "data": {
                    "candidate_id": candidate_id,
                    "error_code": "UNEXPECTED",
                    "error_message": str(e),
                    "trigger": trigger,
                },
            })
            return

        # 3. 解析成功：写 DB + 推 SSE complete
        _update_candidate_status(
            candidate_id, parse_status=2, resume_text=text,
        )
        await sse.publish(candidate_id, {
            "event": "resume_parse_complete",
            "data": {
                "candidate_id": candidate_id,
                "text_length": len(text),
                "parser_used": "pdf" if resume_type == 0 else "docx",
                "trigger": trigger,
            },
        })

    def _update_candidate_status(
        candidate_id: str,
        parse_status: int,
        resume_text: str | None = None,
        parse_error: str | None = None,
    ):
        """更新候选人解析状态（在独立 session 里）"""
        s = SessionLocal()
        try:
            CandidateRepository(s).update_parse_status(
                candidate_id,
                parse_status=parse_status,
                resume_text=resume_text,
                parse_error=parse_error,
            )
            # trigger == "reparse" 时区分 audit log event_type，便于分析
            if parse_status == 2:
                event_type = "resume_parsed"
            elif trigger == "reparse":
                event_type = "resume_reparse_triggered" if parse_status == 1 else "resume_parse_failed"
            else:
                event_type = "resume_parse_failed"
            AuditLogRepository(s).create(
                event_type=event_type,
                actor_id="system",
                actor_type="system",
                candidate_id=candidate_id,
                metadata={"parse_status": parse_status, "error": parse_error, "trigger": trigger},
            )
            s.commit()
        finally:
            s.close()

    # 调度后台任务
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_do_parse_and_update())
    except RuntimeError:
        # 没有 event loop（不太可能），用线程 + asyncio.run
        import threading
        def _run():
            asyncio.run(_do_parse_and_update())
        threading.Thread(target=_run, daemon=True).start()


@router.get("/{candidate_id}", response_model=APIResponse[CandidateOut])
async def get_candidate(
    candidate_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取候选人详情"""
    service = CandidateService(db, actor_id=user.id)
    candidate = service.get_candidate(candidate_id)
    return APIResponse.ok(CandidateOut.model_validate(candidate))


@router.get("/{candidate_id}/resume")
async def download_resume(
    candidate_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """下载候选人简历（PDF）"""
    service = CandidateService(db, actor_id=user.id)
    candidate = service.get_candidate(candidate_id)

    if not candidate.resume_content:
        raise APIError.not_found(
            ErrorCode.RESUME_NOT_FOUND,
            "简历内容为空",
        )

    return Response(
        content=candidate.resume_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=resume_{candidate_id}.pdf"
        },
    )


@router.get("/{candidate_id}/resume-text", response_model=APIResponse[ResumeTextResponse])
async def get_resume_text(
    candidate_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取候选人解析后的简历文本

    状态码：
    - 200: 包含 parse_status 与对应字段（成功=resume_text，失败=parse_error）
    - 404: 候选人不存在
    - 409: 简历仍在解析中（parse_status in (0, 1)）
    """
    service = CandidateService(db, actor_id=user.id)
    candidate = service.get_candidate(candidate_id)

    if candidate.parse_status in (0, 1):
        raise APIError.conflict(
            ErrorCode.RESUME_NOT_PARSED,
            "简历仍在解析中",
        )

    return APIResponse.ok(
        ResumeTextResponse(
            candidate_id=candidate.id,
            parse_status=candidate.parse_status,
            parse_error=candidate.parse_error,
            resume_text=candidate.resume_text,
            is_scanned_document=candidate.is_scanned_document,
            parsed_at=candidate.parsed_at,
            resume_type=candidate.resume_type,
        )
    )


@router.post("/{candidate_id}/reparse", response_model=APIResponse[CandidateCreateResponse])
async def reparse_candidate(
    candidate_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """重新解析候选人简历（复用已存储的原始字节，无需重传）

    状态码：
    - 200: 已重新调度，返回 {parse_status: "parsing"}
    - 404: 候选人不存在
    - 409 RESUME_RETRY_NOT_AVAILABLE: resume_content 为空，无法重试
    - 409 RESUME_NOT_PARSED: 当前正在解析中（parse_status == 1）
    """
    from app.models import CandidateRepository, AuditLogRepository

    service = CandidateService(db, actor_id=user.id)
    candidate = service.get_candidate(candidate_id)

    if not candidate.resume_content:
        raise APIError.conflict(
            ErrorCode.RESUME_RETRY_NOT_AVAILABLE,
            "无法重试，请删除后重新上传",
        )

    if candidate.parse_status == 1:
        raise APIError.conflict(
            ErrorCode.RESUME_NOT_PARSED,
            "正在解析中，请稍候",
        )

    # 复位：清错误、状态置 1、立即提交（保证后续 getResumeText 看到新状态）
    repo = CandidateRepository(db)
    repo.update_parse_status(
        candidate_id,
        parse_status=1,
        resume_text=None,
        parse_error=None,
    )
    AuditLogRepository(db).create(
        event_type="resume_reparse_triggered",
        actor_id=user.id,
        actor_type="user",
        candidate_id=candidate_id,
        metadata={"parse_status": 1, "trigger": "reparse"},
    )
    db.commit()

    # 调度后台任务
    _schedule_parse(
        candidate_id=candidate_id,
        resume_content=candidate.resume_content,
        resume_type=candidate.resume_type,
        trigger="reparse",
    )

    return APIResponse.ok(
        CandidateCreateResponse(
            candidate_id=candidate_id,
            parse_status="parsing",
        )
    )


@router.delete("/{candidate_id}", response_model=APIResponse[dict])
async def delete_candidate(
    candidate_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除候选人（级联删除关联面试）"""
    service = CandidateService(db, actor_id=user.id)
    service.delete_candidate(candidate_id)
    return APIResponse.ok({"status": "deleted", "candidate_id": candidate_id})