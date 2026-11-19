"""
Interviews API（HR 端 + 报告下载，§12）

端点（HR 端，JWT 鉴权）：
- GET    /api/interviews              列表
- POST   /api/interviews              创建
- GET    /api/interviews/{id}         详情
- PUT    /api/interviews/{id}         更新
- DELETE /api/interviews/{id}         删除
- GET    /api/interviews/{id}/report  下载 PDF 报告
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.interview import (
    InterviewCreate,
    InterviewUpdate,
    InterviewOut,
    InterviewListResponse,
    InterviewCreateResponse,
)
from app.schemas.response import APIResponse
from app.services.interview_service import InterviewService


router = APIRouter(prefix="/api/interviews", tags=["interviews"])


@router.get("", response_model=APIResponse[InterviewListResponse])
async def list_interviews(
    candidate_id: str | None = Query(default=None),
    position_id: int | None = Query(default=None),
    status: int | None = Query(default=None, ge=0, le=4),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取面试列表"""
    service = InterviewService(db, actor_id=user.id)
    skip = (page - 1) * page_size
    items, total = service.list_interviews(
        candidate_id=candidate_id,
        position_id=position_id,
        status=status,
        skip=skip,
        limit=page_size,
    )
    return APIResponse.ok(
        InterviewListResponse(
            items=[InterviewOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", response_model=APIResponse[InterviewCreateResponse], status_code=201)
async def create_interview(
    data: InterviewCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建面试（自动启动 LangGraph 工作流 + 发送候选人邀请邮件）"""
    from app.models import CandidateRepository, PositionRepository

    service = InterviewService(db, actor_id=user.id)
    interview = service.create_interview(
        candidate_id=data.candidate_id,
        position_id=data.position_id,
        interviewer=data.interviewer,
        start_time=data.start_time,
    )

    # 启动 LangGraph 工作流（后台线程，不阻塞 API）
    from app.services.workflow_service import run_for_interview
    run_for_interview(
        interview_id=interview.id,
        thread_id=interview.langgraph_thread_id,
    )

    # 发送候选人邀请邮件（best-effort，失败不阻塞）
    _send_invite_email(db, interview)

    return APIResponse.ok(
        InterviewCreateResponse(
            id=interview.id,
            token=interview.token,
            status=interview.status,
        )
    )


def _send_invite_email(db: Session, interview) -> None:
    """发送面试邀请邮件（best-effort）"""
    from app.models import CandidateRepository, PositionRepository
    from app.services.email_service import send_interview_invite
    from app.config import settings
    import logging

    logger = logging.getLogger(__name__)

    try:
        candidate = CandidateRepository(db).get(interview.candidate_id)
        position = PositionRepository(db).get(interview.position_id)
        if not candidate or not position or not candidate.email:
            return

        # 构造候选人 URL（Week 3 改成真实域名）
        base_url = "http://localhost:5173"  # dev
        interview_url = f"{base_url}/candidate-portal?token={interview.token}"

        send_interview_invite(
            to_email=candidate.email,
            candidate_name=candidate.name,
            position_name=position.name,
            interview_url=interview_url,
        )
        logger.info("invite_email_sent", extra={"interview_id": interview.id})
    except Exception as e:
        logger.warning(
            "invite_email_failed",
            extra={"interview_id": interview.id, "error": str(e)},
        )


@router.get("/{interview_id}", response_model=APIResponse[InterviewOut])
async def get_interview(
    interview_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取面试详情"""
    service = InterviewService(db, actor_id=user.id)
    interview = service.get_interview(interview_id)
    return APIResponse.ok(InterviewOut.model_validate(interview))


@router.put("/{interview_id}", response_model=APIResponse[InterviewOut])
async def update_interview(
    interview_id: int,
    data: InterviewUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新面试"""
    service = InterviewService(db, actor_id=user.id)
    interview = service.update_interview(
        interview_id,
        interviewer=data.interviewer,
        start_time=data.start_time,
        is_passed=data.is_passed,
        status=data.status,
    )
    return APIResponse.ok(InterviewOut.model_validate(interview))


@router.delete("/{interview_id}", response_model=APIResponse[dict])
async def delete_interview(
    interview_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除面试（级联删除题目）"""
    service = InterviewService(db, actor_id=user.id)
    service.delete_interview(interview_id)
    return APIResponse.ok({"status": "deleted", "interview_id": interview_id})


@router.get("/{interview_id}/report")
async def download_report(
    interview_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """下载面试报告 PDF"""
    service = InterviewService(db, actor_id=user.id)
    pdf_bytes, file_name = service.download_report(interview_id)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={file_name}"
        },
    )