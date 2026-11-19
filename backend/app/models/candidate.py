"""
Candidate 模型 + Repository

候选人实体。HR 添加候选人 + 上传简历（§11）。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.database import Base
from app.models.position import Position


class Candidate(Base):
    """候选人"""
    __tablename__ = "candidates"

    # ===== 主键（UUID 字符串，§11 决策）=====
    id: Mapped[str] = mapped_column(String, primary_key=True)

    # ===== 业务字段 =====
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    email: Mapped[str] = mapped_column(String, index=True)

    # ===== 简历存储（§11.4）=====
    # 0=PDF / 1=Word（沿用老项目编码）
    resume_type: Mapped[int] = mapped_column(Integer)
    # 老 BLOB 字段（保留兼容，Phase 4 切文件后废弃）
    resume_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # 新文件路径（Week 2 起新写入用）
    resume_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # ===== 解析状态（§11 新增字段）=====
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 0=待解析 / 1=解析中 / 2=成功 / 3=失败
    parse_status: Mapped[int] = mapped_column(Integer, default=0)
    parse_error: Mapped[str | None] = mapped_column(String, nullable=True)
    is_scanned_document: Mapped[bool] = mapped_column(Boolean, default=False)
    parsed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ===== 上传审计 =====
    uploaded_by: Mapped[str] = mapped_column(String)  # HR 用户 ID
    uploaded_at: Mapped[int] = mapped_column(Integer, default=lambda: int(datetime.utcnow().timestamp()))

    # ===== 时间戳 =====
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(datetime.utcnow().timestamp()))
    updated_at: Mapped[int] = mapped_column(
        Integer,
        default=lambda: int(datetime.utcnow().timestamp()),
        onupdate=lambda: int(datetime.utcnow().timestamp()),
    )

    # ===== 关系 =====
    # position = relationship("Position", back_populates="candidates")  # 暂不启用，需要 Position 加反向关系

    def __repr__(self) -> str:
        return f"<Candidate {self.id[:8]}: {self.name} ({self.parse_status})>"


# ===== Repository =====
class CandidateRepository:
    """Candidate 数据访问层"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, candidate_id: str) -> Candidate | None:
        return self.db.query(Candidate).filter(Candidate.id == candidate_id).first()

    def get_by_token(self, token: str):
        """通过候选人 token 反查（实际通过 Interview 表，候选人入口不直接查 candidate）"""
        # 保留接口一致性；token 验证在 InterviewRepository
        raise NotImplementedError("Use InterviewRepository.get_by_token()")

    def list_by_position(
        self,
        position_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Candidate]:
        return (
            self.db.query(Candidate)
            .filter(Candidate.position_id == position_id)
            .order_by(Candidate.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Candidate]:
        return (
            self.db.query(Candidate)
            .order_by(Candidate.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(
        self,
        id: str,
        position_id: int,
        name: str,
        email: str,
        resume_type: int,
        uploaded_by: str,
        resume_path: str | None = None,
        resume_content: bytes | None = None,
    ) -> Candidate:
        now = int(datetime.utcnow().timestamp())
        candidate = Candidate(
            id=id,
            position_id=position_id,
            name=name,
            email=email,
            resume_type=resume_type,
            resume_path=resume_path,
            resume_content=resume_content,
            parse_status=1,  # 解析中
            uploaded_by=uploaded_by,
            uploaded_at=now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def update(
        self,
        candidate_id: str,
        **kwargs,
    ) -> Candidate | None:
        """更新候选人字段（部分字段）"""
        candidate = self.get(candidate_id)
        if not candidate:
            return None
        for key, value in kwargs.items():
            if hasattr(candidate, key):
                setattr(candidate, key, value)
        candidate.updated_at = int(datetime.utcnow().timestamp())
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def update_parse_status(
        self,
        candidate_id: str,
        parse_status: int,
        resume_text: str | None = None,
        parse_error: str | None = None,
    ) -> Candidate | None:
        """更新解析状态（§11 专用方法）"""
        candidate = self.get(candidate_id)
        if not candidate:
            return None
        candidate.parse_status = parse_status
        if resume_text is not None:
            candidate.resume_text = resume_text
        if parse_error is not None:
            candidate.parse_error = parse_error
        candidate.parsed_at = int(datetime.utcnow().timestamp())
        candidate.updated_at = candidate.parsed_at
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def delete(self, candidate_id: str) -> bool:
        candidate = self.get(candidate_id)
        if not candidate:
            return False
        self.db.delete(candidate)
        # 不在这里commit，由service层统一提交
        return True