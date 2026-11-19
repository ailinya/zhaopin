"""
Interview 业务服务层（§1.1 + §12）

业务规则：
- 创建面试时自动启动 LangGraph（Week 2 启用，目前只创建不启动）
- 删除面试时级联删除题目
- 候选人只读 token URL 鉴权
- 状态机校验（防止非法跃迁）
"""
from typing import BinaryIO
from sqlalchemy.orm import Session

from app.core.errors import APIError, ErrorCode
from app.models import (
    Interview, InterviewRepository,
    CandidateRepository, PositionRepository,
    InterviewQuestionRepository, AuditLogRepository,
)


class InterviewService:
    """Interview 业务服务"""

    def __init__(self, db: Session, actor_id: str = "system"):
        self.db = db
        self.repo = InterviewRepository(db)
        self.audit = AuditLogRepository(db)
        self.actor_id = actor_id  # ← 补上漏掉的赋值

    def list_interviews(
        self,
        candidate_id: str | None = None,
        position_id: int | None = None,
        status: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Interview], int]:
        items = self.repo.list_all(
            candidate_id=candidate_id,
            position_id=position_id,
            status=status,
            skip=skip,
            limit=limit,
        )
        total = len(self.repo.list_all(
            candidate_id=candidate_id,
            position_id=position_id,
            status=status,
            skip=0,
            limit=10000,
        ))
        return items, total

    def get_interview(self, interview_id: int) -> Interview:
        interview = self.repo.get(interview_id)
        if not interview:
            raise APIError.not_found(
                ErrorCode.INTERVIEW_NOT_FOUND,
                f"面试 {interview_id} 不存在",
            )
        return interview

    def get_by_token(self, token: str) -> Interview:
        """通过候选人 URL token 获取面试（§14.7 鉴权用）"""
        interview = self.repo.get_by_token(token)
        if not interview:
            raise APIError.not_found(
                ErrorCode.INTERVIEW_NOT_FOUND,
                "面试链接无效或已过期",
            )
        return interview

    def create_interview(
        self,
        candidate_id: str,
        position_id: int | None = None,
        interviewer: str | None = None,
        start_time: int | None = None,
    ) -> Interview:
        """创建面试（Week 2 会在这里启动 LangGraph，目前只创建）"""
        # 验证候选人存在
        candidate = CandidateRepository(self.db).get(candidate_id)
        if not candidate:
            raise APIError.not_found(
                ErrorCode.CANDIDATE_NOT_FOUND,
                f"候选人 {candidate_id} 不存在",
            )

        # 如果没传 position_id，从 candidate 反查
        if position_id is None:
            position_id = candidate.position_id

        # 验证岗位
        position = PositionRepository(self.db).get(position_id)
        if not position:
            raise APIError.not_found(
                ErrorCode.POSITION_NOT_FOUND,
                f"岗位 {position_id} 不存在",
            )

        # 默认 start_time = now
        if start_time is None:
            import time
            start_time = int(time.time())

        interview = self.repo.create(
            candidate_id=candidate_id,
            position_id=position_id,
            start_time=start_time,
            interviewer=interviewer,
        )

        self.audit.create(
            event_type="interview_created",
            actor_id=self.actor_id,
            actor_type="user",
            interview_id=interview.id,
            candidate_id=candidate_id,
            metadata={
                "position_id": position_id,
                "interviewer": interviewer,
                "token": interview.token,
            },
        )

        # TODO Week 2: 触发 LangGraph workflow
        # from app.services.workflow_service import workflow_service
        # await workflow_service.run_for_interview(interview.id)

        return interview

    def update_interview(
        self,
        interview_id: int,
        interviewer: str | None = None,
        start_time: int | None = None,
        is_passed: int | None = None,
        status: int | None = None,
    ) -> Interview:
        """更新面试（部分字段）"""
        interview = self.get_interview(interview_id)

        if status is not None and status != interview.status:
            # 状态机校验（§10.3）
            self._validate_state_transition(interview.status, status)

        # 用 SQLAlchemy 直接更新
        if interviewer is not None:
            interview.interviewer = interviewer
        if start_time is not None:
            interview.start_time = start_time
        if is_passed is not None:
            interview.is_passed = is_passed
        if status is not None:
            interview.status = status

        self.db.commit()
        self.db.refresh(interview)

        self.audit.create(
            event_type="interview_updated",
            actor_id=self.actor_id,
            actor_type="user",
            interview_id=interview_id,
        )
        return interview

    def _validate_state_transition(self, from_status: int, to_status: int) -> None:
        """状态机跃迁校验（§10.3）"""
        valid_transitions = {
            0: {1, 4},           # 未开始 → 试题已备好 / 报告已生成（异常路径）
            1: {2, 3, 4},        # 试题已备好 → 进行中 / 完毕 / 报告已生成
            2: {3},              # 进行中 → 完毕
            3: {4},              # 完毕 → 报告已生成
            4: set(),            # 终态
        }

        if to_status not in valid_transitions.get(from_status, set()):
            raise APIError.conflict(
                ErrorCode.INVALID_STATE_TRANSITION,
                f"非法状态跃迁: {from_status} → {to_status}",
            )

    def delete_interview(self, interview_id: int) -> None:
        """删除面试（级联删除题目）"""
        interview = self.get_interview(interview_id)

        # 级联删除题目
        InterviewQuestionRepository(self.db).delete_by_interview(interview_id)
        self.repo.delete(interview_id)

        self.audit.create(
            event_type="interview_deleted",
            actor_id=self.actor_id,
            actor_type="user",
            interview_id=interview_id,
            metadata={"candidate_id": interview.candidate_id},
        )

    def download_report(self, interview_id: int) -> tuple[bytes, str]:
        """下载面试报告 PDF

        优先从 report_path 读文件（当前节点 D 的写入路径），
        回退到 report_content BLOB（兼容老数据）。
        """
        from pathlib import Path
        interview = self.get_interview(interview_id)

        if interview.status < 4:
            raise APIError.conflict(
                ErrorCode.INVALID_STATE_TRANSITION,
                "报告尚未生成",
            )

        # 优先从磁盘文件读（节点 D 当前走 file_storage.save_report）
        if interview.report_path:
            path = Path(interview.report_path)
            if path.exists() and path.is_file():
                return path.read_bytes(), f"interview_report_{interview.id}.pdf"

        # 回退到 DB BLOB（老数据可能只有 BLOB 没有 path，或 path 失效）
        if interview.report_content:
            return interview.report_content, f"interview_report_{interview.id}.pdf"

        raise APIError.not_found(
            ErrorCode.REPORT_NOT_FOUND,
            "报告内容为空",
        )