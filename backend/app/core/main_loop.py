"""
全局 asyncio event loop 引用（§4 行动项 #1）

用于从后台线程（Whisper / LLM / PDF 渲染）安全地调度 asyncio 协程
（如 SSE 推送）。

典型用法：
    from app.core import main_loop
    import asyncio

    def background_worker_push_sse(interview_id, event):
        asyncio.run_coroutine_threadsafe(
            sse_manager.publish(interview_id, event),
            main_loop.loop,  # ← 必须，缺这个会报 "no running event loop"
        )

在 lifespan 启动时由 main.py 调用 set_main_loop() 赋值。
"""
import asyncio
from typing import Optional

loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_loop(loop_: asyncio.AbstractEventLoop) -> None:
    """设置全局 event loop 引用（lifespan 启动时调用）"""
    global loop
    loop = loop_


def get_main_loop() -> asyncio.AbstractEventLoop:
    """获取全局 event loop（运行时使用）"""
    if loop is None:
        raise RuntimeError(
            "Main event loop not set. "
            "Did you forget to call set_main_loop() in lifespan?"
        )
    return loop