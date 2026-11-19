"""
Candidate 业务服务层（§1.1 + §11）

业务规则：
- 创建候选人时上传简历（PDF/DOCX），触发后台解析
- 删除候选人时级联删除关联面试
- 解析状态管理
"""
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.errors import APIError, ErrorCode
from app.models import (
    Candidate, CandidateRepository,
    PositionRepository, AuditLogRepository,
)


class CandidateService:
    """Candidate 业务服务"""

    def __init__(self, db: Session, actor_id: str = "system"):
        self.db = db
        self.actor_id = actor_id
        self.repo = CandidateRepository(db)
        self.audit = AuditLogRepository(db)

    def list_candidates(
        self,
        position_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Candidate], int]:
        """获取候选人列表 + 总数"""
        if position_id is not None:
            items = self.repo.list_by_position(position_id, skip=skip, limit=limit)
            total = len(self.repo.list_by_position(position_id, skip=0, limit=10000))
        else:
            items = self.repo.list_all(skip=skip, limit=limit)
            total = len(self.repo.list_all(skip=0, limit=10000))
        return items, total

    def get_candidate(self, candidate_id: str) -> Candidate:
        """获取候选人"""
        candidate = self.repo.get(candidate_id)
        if not candidate:
            raise APIError.not_found(
                ErrorCode.CANDIDATE_NOT_FOUND,
                f"候选人 {candidate_id} 不存在",
            )
        return candidate

    def create_candidate(
        self,
        position_id: int,
        name: str,
        email: str,
        resume_type: int,
        resume_content: bytes | None = None,
        resume_path: str | None = None,
        uploaded_by: str = "system",
    ) -> Candidate:
        """创建候选人（不直接触发后台解析，调用方负责）"""
        # 验证
        if not name or not name.strip():
            raise APIError.bad_request(ErrorCode.PARAM_MISSING, "姓名不能为空")
        if not email or "@" not in email:
            raise APIError.bad_request(ErrorCode.PARAM_FORMAT_ERROR, "邮箱格式错误")
        if resume_type not in (0, 1):
            raise APIError.bad_request(ErrorCode.PARAM_OUT_OF_RANGE, "resume_type 必须是 0/1")

        # 验证岗位存在
        position = PositionRepository(self.db).get(position_id)
        if not position:
            raise APIError.not_found(
                ErrorCode.POSITION_NOT_FOUND,
                f"岗位 {position_id} 不存在",
            )

        candidate_id = str(uuid.uuid4())
        candidate = self.repo.create(
            id=candidate_id,
            position_id=position_id,
            name=name.strip(),
            email=email.strip(),
            resume_type=resume_type,
            resume_content=resume_content,
            resume_path=resume_path,
            uploaded_by=uploaded_by,
        )

        self.audit.create(
            event_type="candidate_created",
            actor_id=uploaded_by,
            actor_type="user",
            candidate_id=candidate_id,
            metadata={
                "position_id": position_id,
                "name": name,
                "has_resume": resume_content is not None or resume_path is not None,
            },
        )
        return candidate

    def delete_candidate(self, candidate_id: str) -> None:
        """删除候选人（级联删除关联面试）"""
        candidate = self.get_candidate(candidate_id)

        # 级联删除面试（和题目）
        from app.models.interview import InterviewRepository
        from app.models.interview_question import InterviewQuestionRepository

        interview_repo = InterviewRepository(self.db)
        question_repo = InterviewQuestionRepository(self.db)

        interviews = interview_repo.list_all(candidate_id=candidate_id)
        deleted_interview_count = 0
        for interview in interviews:
            question_repo.delete_by_interview(interview.id)
            interview_repo.delete(interview.id)
            deleted_interview_count += 1

        # 删除候选人（不自动commit）
        candidate_obj = self.repo.get(candidate_id)
        if candidate_obj:
            self.db.delete(candidate_obj)

        # 创建审计日志
        self.audit.create(
            event_type="candidate_deleted",
            actor_id=self.actor_id,
            actor_type="user",
            metadata={
                "candidate_id": candidate_id,
                "name": candidate.name,
                "deleted_interviews": deleted_interview_count,
            },
        )

        # 一次性提交所有更改
        self.db.commit()

    def update_parse_status(
        self,
        candidate_id: str,
        parse_status: int,
        resume_text: str | None = None,
        parse_error: str | None = None,
    ) -> Candidate:
        """更新简历解析状态（§11 后台线程调用）"""
        return self.repo.update_parse_status(
            candidate_id, parse_status, resume_text, parse_error
        )