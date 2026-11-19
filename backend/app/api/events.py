"""
Events API（SSE 端点，§5 + §13.6）

端点（HR 端，JWT 鉴权）：
- GET /api/interviews/{id}/events

建立 SSE 长连接，订阅该面试的所有事件。
Nginx 需配置 SSE 优化（详见 nginx.conf）。
"""
import asyncio
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.errors import APIError, ErrorCode
from app.deps import get_db, get_current_user, get_sse_manager_dep
from app.models.user import User
from app.services.interview_service import InterviewService
from app.services.sse_manager import SSEManager


router = APIRouter(prefix="/api/interviews", tags=["events"])


@router.get("/{interview_id}/events")
async def stream_events(
    interview_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    sse_manager: SSEManager = Depends(get_sse_manager_dep),
):
    """SSE 端点：订阅面试事件流"""
    # 验证面试存在
    InterviewService(db, actor_id=user.id).get_interview(interview_id)

    async def event_generator():
        """SSE 事件生成器"""
        try:
            # 立即发送连接成功事件
            yield f"event: connected\ndata: {json.dumps({'event': 'connected', 'interview_id': interview_id, 'timestamp': asyncio.get_event_loop().time()})}\n\n"

            # 订阅事件流
            async for event in sse_manager.subscribe(interview_id):
                event_str = json.dumps(event, ensure_ascii=False)
                event_name = event.get("event", "message")
                yield f"event: {event_name}\ndata: {event_str}\n\n"

                # 心跳保活（Nginx 不会切断）
                # 实际心跳由客户端检测断线后重连
        except asyncio.CancelledError:
            # 客户端断开
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx：禁用缓冲
        },
    )