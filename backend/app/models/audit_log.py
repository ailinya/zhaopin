"""
AuditLog 模型 + Repository

审计日志（§4 行动项 + §16.2）。

记录所有关键状态变更和操作：
- interview_created / resume_uploaded / resume_parsed
- questions_generated / answer_submitted / report_generated
- user_login / token_refresh / etc.

用途：
1. 状态机审计（出问题可回溯）
2. 幂等性查询（Idempotency-Key 检查）
3. 合规审计（个人信息处理记录）
"""
from datetime import datetime
from typing import Any
import json

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.database import Base


class AuditLog(Base):
    """审计日志"""
    __tablename__ = "audit_logs"

    # ===== 主键 =====
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ===== 事件类型 =====
    # 见 §5 SSE 事件清单 + §4 行动项
    event_type: Mapped[str] = mapped_column(String, index=True)

    # ===== 关联资源 =====
    # 关联的面试 / 候选人 / 用户 ID（多对一）
    interview_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    candidate_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)

    # ===== 行为者 =====
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_type: Mapped[str] = mapped_column(String, default="user")  # "user" / "system" / "candidate"

    # ===== 元数据 =====
    # 任意 JSON 数据（键值对）
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    # ===== 时间 =====
    occurred_at: Mapped[int] = mapped_column(Integer, default=lambda: int(datetime.utcnow().timestamp()), index=True)

    def __repr__(self) -> str:
        return f"<AuditLog {self.id}: {self.event_type} at {self.occurred_at}>"

    @property
    def metadata_dict(self) -> dict[str, Any]:
        """解析 metadata_json 为 dict"""
        try:
            return json.loads(self.metadata_json) if self.metadata_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}


# ===== Repository =====
class AuditLogRepository:
    """AuditLog 数据访问层"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        event_type: str,
        actor_id: str | None = None,
        actor_type: str = "user",
        interview_id: int | None = None,
        candidate_id: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """记录一条审计日志"""
        log = AuditLog(
            event_type=event_type,
            actor_id=actor_id,
            actor_type=actor_type,
            interview_id=interview_id,
            candidate_id=candidate_id,
            user_id=user_id,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
            occurred_at=int(datetime.utcnow().timestamp()),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def find_idempotent(
        self,
        event_type: str,
        actor_id: str | None,
        idempotency_key: str,
    ) -> AuditLog | None:
        """幂等性查询：检查给定 Idempotency-Key 是否已处理过

        Returns:
            已处理的 AuditLog（如存在），None（如不存在）
        """
        from sqlalchemy import or_, and_

        # 简单实现：查 actor + event_type + 时间窗口内的 metadata 包含 idempotency_key
        # 生产环境可加 Redis 缓存层
        logs = (
            self.db.query(AuditLog)
            .filter(AuditLog.event_type == event_type)
            .filter(AuditLog.actor_id == actor_id)
            .all()
        )
        for log in logs:
            meta = log.metadata_dict
            if meta.get("idempotency_key") == idempotency_key:
                return log
        return None

    def list_by_interview(
        self,
        interview_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        """查面试的全部审计日志（按时间倒序）"""
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.interview_id == interview_id)
            .order_by(AuditLog.occurred_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_by_candidate(
        self,
        candidate_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        """查候选人的全部审计日志"""
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.candidate_id == candidate_id)
            .order_by(AuditLog.occurred_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )