"""
SQLAlchemy ORM 模型集中导入

任何需要"知道所有模型"的地方（init_db / Alembic env.py）都从这里 import。
"""
from app.models.base import Base
from app.models.user import User, UserRepository
from app.models.position import Position, PositionRepository
from app.models.candidate import Candidate, CandidateRepository
from app.models.interview import Interview, InterviewRepository
from app.models.interview_question import InterviewQuestion, InterviewQuestionRepository
from app.models.audit_log import AuditLog, AuditLogRepository

__all__ = [
    # Base
    "Base",
    # Models
    "User",
    "Position",
    "Candidate",
    "Interview",
    "InterviewQuestion",
    "AuditLog",
    # Repositories
    "UserRepository",
    "PositionRepository",
    "CandidateRepository",
    "InterviewRepository",
    "InterviewQuestionRepository",
    "AuditLogRepository",
]