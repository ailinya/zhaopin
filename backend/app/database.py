"""
SQLAlchemy 2.0 数据库配置

- DeclarativeBase 声明基类
- Engine 单例（SQLite WAL 模式）
- SessionLocal 工厂
- get_db FastAPI 依赖
- init_db 初始化（导入所有 model 后建表）
"""
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


# ===== DeclarativeBase =====
class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明基类"""
    pass


# ===== Engine =====
def _create_engine():
    """根据 DATABASE_URL 创建 engine（SQLite WAL 模式）"""
    connect_args = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        # SQLite 允许多线程访问（WAL 模式）
        connect_args = {"check_same_thread": False}

    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        connect_args=connect_args,
        pool_pre_ping=True,  # 连接前 ping，防 stale connection
    )

    # SQLite 启用 WAL 模式 + 设置 busy_timeout
    if settings.DATABASE_URL.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """连接时设置 PRAGMA"""
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")  # WAL 模式（并发读不阻塞写）
            cursor.execute("PRAGMA foreign_keys=ON")   # 启用外键
            cursor.execute("PRAGMA busy_timeout=5000") # 锁等待 5s
            cursor.close()

    return engine


engine = _create_engine()


# ===== SessionLocal =====
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# ===== FastAPI 依赖 =====
def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每次请求一个 Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===== 初始化 =====
def init_db() -> None:
    """初始化数据库表（Day 2 已接入所有 model）"""
    # 确保 SQLite DB 文件所在目录存在
    if settings.DATABASE_URL.startswith("sqlite"):
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # 导入所有 model（让 SQLAlchemy 知道它们）
    from app.models import (
        User,
        Position,
        Candidate,
        Interview,
        InterviewQuestion,
        AuditLog,
    )  # noqa: F401

    # 创建所有表
    Base.metadata.create_all(bind=engine)