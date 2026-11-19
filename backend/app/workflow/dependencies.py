"""
Workflow 节点依赖（DI 容器，Day 3 重构）

节点不再 `from app.database import SessionLocal`，改为接收 deps 参数。
这样测试可以注入 mock deps，不需要真实的 DB。
"""
from dataclasses import dataclass
from typing import Any
from sqlalchemy.orm import Session

from app.models import (
    InterviewRepository, CandidateRepository, PositionRepository,
    InterviewQuestionRepository, AuditLogRepository,
)
from app.services.file_storage import FileStorage
from app.services.sse_manager import SSEManager


@dataclass
class WorkflowDeps:
    """工作流节点依赖（test 时可注入 mock）"""
    db: Session
    interview_repo: InterviewRepository
    candidate_repo: CandidateRepository
    position_repo: PositionRepository
    question_repo: InterviewQuestionRepository
    audit_repo: AuditLogRepository
    file_storage: FileStorage
    sse_manager: SSEManager
    prompt_renderer: Any  # workflow_service.render_prompt
    # LLM service functions are called via lazy import inside nodes
    # (test 时通过 patch app.workflow.nodes.chat_json 拦截)

    def close(self):
        """关闭 DB session（生命周期结束）"""
        if self.db:
            self.db.close()


def build_deps_from_db(db: Session) -> WorkflowDeps:
    """从 DB session 构造完整的 WorkflowDeps（生产环境用）"""
    from app.services.file_storage import get_file_storage
    from app.services.sse_manager import get_sse_manager
    from app.services import workflow_service

    return WorkflowDeps(
        db=db,
        interview_repo=InterviewRepository(db),
        candidate_repo=CandidateRepository(db),
        position_repo=PositionRepository(db),
        question_repo=InterviewQuestionRepository(db),
        audit_repo=AuditLogRepository(db),
        file_storage=get_file_storage(),
        sse_manager=get_sse_manager(),
        prompt_renderer=workflow_service.render_prompt,
    )