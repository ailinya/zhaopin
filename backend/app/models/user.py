"""
User 模型 + Repository

用于 HR 端鉴权（§14）。
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.database import Base
from app.core.security import hash_password


class User(Base):
    """HR 管理员用户"""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID 字符串
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[int] = mapped_column(Integer)  # Unix timestamp (秒)
    last_login_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<User {self.username} ({'active' if self.is_active else 'disabled'})>"


# ===== Repository =====
class UserRepository:
    """User 数据访问层（与 ORM 同文件，§1.2 决策）"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: str) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> User | None:
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def create(
        self,
        id: str,
        username: str,
        email: str,
        password: str,
        full_name: str | None = None,
        is_admin: bool = False,
    ) -> User:
        """创建用户（自动 hash 密码）"""
        user = User(
            id=id,
            username=username,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            is_admin=is_admin,
            is_active=True,
            created_at=int(datetime.utcnow().timestamp()),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_last_login(self, user_id: str) -> None:
        """更新最后登录时间"""
        user = self.get(user_id)
        if user:
            user.last_login_at = int(datetime.utcnow().timestamp())
            self.db.commit()

    def list_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        return self.db.query(User).offset(skip).limit(limit).all()