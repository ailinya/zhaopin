"""
Position 模型 + Repository

岗位实体。HR 创建招聘岗位。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.database import Base


class Position(Base):
    """招聘岗位"""
    __tablename__ = "positions"

    # ===== 主键 =====
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ===== 业务字段 =====
    name: Mapped[str] = mapped_column(String, index=True)
    requirements: Mapped[str] = mapped_column(Text, default="")
    responsibilities: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    # ===== 状态 =====
    # 0=未启动 / 1=进行中 / 2=已完成
    status: Mapped[int] = mapped_column(Integer, default=0)

    # ===== 元数据 =====
    recruiter: Mapped[str | None] = mapped_column(String, nullable=True)  # HR 用户名

    # ===== 时间戳 =====
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(datetime.utcnow().timestamp()))
    updated_at: Mapped[int] = mapped_column(
        Integer,
        default=lambda: int(datetime.utcnow().timestamp()),
        onupdate=lambda: int(datetime.utcnow().timestamp()),
    )

    def __repr__(self) -> str:
        return f"<Position {self.id}: {self.name} ({self.status})>"


# ===== Repository =====
class PositionRepository:
    """Position 数据访问层"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, position_id: int) -> Position | None:
        return self.db.query(Position).filter(Position.id == position_id).first()

    def list_all(
        self,
        status: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Position]:
        query = self.db.query(Position)
        if status is not None:
            query = query.filter(Position.status == status)
        return query.order_by(Position.id.desc()).offset(skip).limit(limit).all()

    def create(
        self,
        name: str,
        requirements: str = "",
        responsibilities: str = "",
        quantity: int = 1,
        status: int = 0,
        recruiter: str | None = None,
    ) -> Position:
        now = int(datetime.utcnow().timestamp())
        position = Position(
            name=name,
            requirements=requirements,
            responsibilities=responsibilities,
            quantity=quantity,
            status=status,
            recruiter=recruiter,
            created_at=now,
            updated_at=now,
        )
        self.db.add(position)
        self.db.commit()
        self.db.refresh(position)
        return position

    def update(
        self,
        position_id: int,
        name: str | None = None,
        requirements: str | None = None,
        responsibilities: str | None = None,
        quantity: int | None = None,
        status: int | None = None,
        recruiter: str | None = None,
    ) -> Position | None:
        position = self.get(position_id)
        if not position:
            return None
        if name is not None:
            position.name = name
        if requirements is not None:
            position.requirements = requirements
        if responsibilities is not None:
            position.responsibilities = responsibilities
        if quantity is not None:
            position.quantity = quantity
        if status is not None:
            position.status = status
        if recruiter is not None:
            position.recruiter = recruiter
        position.updated_at = int(datetime.utcnow().timestamp())
        self.db.commit()
        self.db.refresh(position)
        return position

    def delete(self, position_id: int) -> bool:
        position = self.get(position_id)
        if not position:
            return False
        self.db.delete(position)
        self.db.commit()
        return True