"""
LangGraph Checkpointer 工厂（§10.7）

MVP：SqliteSaver（持久化到 SQLite DB）
Phase 5：可换 PostgresSaver（生产多副本部署）
"""
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator

from langgraph.checkpoint.sqlite import SqliteSaver


_checkpointer = None


@contextmanager
def get_checkpointer() -> Iterator[SqliteSaver]:
    """
    获取 checkpointer（上下文管理器）

    SqliteSaver.from_conn_string 返回 Iterator，需要作为上下文管理器使用
    """
    global _checkpointer

    # 实际文件路径：./backend/workflow_checkpoints.db
    # 与业务 DB 分离
    backend_dir = Path(__file__).resolve().parent.parent
    cp_path = backend_dir / "workflow_checkpoints.db"

    # 使用 with 语句获取 saver
    with SqliteSaver.from_conn_string(f"sqlite:///{cp_path.as_posix()}") as saver:
        yield saver


def get_checkpointer_sync() -> SqliteSaver:
    """同步获取 checkpointer（单例模式，用于 compile）"""
    global _checkpointer
    if _checkpointer is None:
        import sqlite3
        backend_dir = Path(__file__).resolve().parent.parent
        cp_path = backend_dir / "workflow_checkpoints.db"
        # 直接使用 sqlite3 连接
        # check_same_thread=False: LangGraph 在 background thread 用 saver 实例时需要
        # 这是 MVP 的简化方案；生产建议用 PostgresSaver
        conn = sqlite3.connect(str(cp_path.absolute()), check_same_thread=False)
        _checkpointer = SqliteSaver(conn)
    return _checkpointer


def reset_checkpointer():
    """重置 checkpointer（测试用）"""
    global _checkpointer
    if _checkpointer is not None:
        try:
            _checkpointer.__exit__(None, None, None)
        except Exception:
            pass
    _checkpointer = None