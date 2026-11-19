"""
SSE Manager（§5 + §10.6 + §13.6）

借鉴 AgentTeamProject 的 core/sse.py 模式（§3.3）：
- asyncio.Queue per interview_id（pub/sub）
- subscribe() 返回 AsyncGenerator
- publish() 广播事件
- close_session() 发 sentinel 关闭

用法：
    sse_manager = SSEManager()

    # 发送端（service / 后台线程）
    await sse_manager.publish(interview_id, {"event": "status_changed", ...})

    # 接收端（FastAPI 端点）
    async def event_generator():
        async for event in sse_manager.subscribe(interview_id):
            yield event
"""
import asyncio
import json
from typing import AsyncGenerator


class SSEManager:
    """SSE 事件管理器（asyncio.Queue pub/sub）"""

    def __init__(self) -> None:
        # session_id (interview_id) → set of queues
        self._subscribers: dict[int, set[asyncio.Queue]] = {}

    async def subscribe(self, interview_id: int) -> AsyncGenerator[dict, None]:
        """订阅 interview_id 的事件流

        Yield 格式：{"event": "...", "data": {...}}
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.setdefault(interview_id, set()).add(queue)

        try:
            while True:
                # 等待事件（队列满时丢弃最老的）
                event = await queue.get()
                if event is None:
                    # Sentinel: 关闭信号
                    break
                yield event
        finally:
            self._subscribers.get(interview_id, set()).discard(queue)

    async def publish(self, interview_id: int, event: dict) -> None:
        """发布事件到指定 interview_id 的所有订阅者"""
        # 序列化（确保 JSON 可序列化）
        try:
            event_str = json.dumps(event, ensure_ascii=False, default=str)
            event_obj = json.loads(event_str)
        except (TypeError, ValueError):
            # 不可序列化的字段降级为 str
            event_obj = {k: str(v) for k, v in event.items()}

        formatted = {"event": event_obj.get("event", "message"), "data": event_obj}

        # 推给所有订阅者
        subscribers = self._subscribers.get(interview_id, set())
        for queue in list(subscribers):
            try:
                queue.put_nowait(formatted)
            except asyncio.QueueFull:
                # 队列满，丢弃这个事件（避免阻塞）
                pass

    def close_session(self, interview_id: int) -> None:
        """关闭 interview 的所有订阅连接（Sentinel 推送）"""
        subscribers = self._subscribers.get(interview_id, set())
        for queue in list(subscribers):
            try:
                queue.put_nowait(None)  # Sentinel
            except asyncio.QueueFull:
                pass


# ===== 全局单例 =====
_sse_manager: SSEManager | None = None


def get_sse_manager() -> SSEManager:
    """获取全局 SSE Manager 单例"""
    global _sse_manager
    if _sse_manager is None:
        _sse_manager = SSEManager()
    return _sse_manager