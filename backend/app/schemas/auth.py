"""
Auth Schemas

登录、刷新、用户相关 Pydantic 模型。
"""
from typing import Optional

from pydantic import BaseModel


# ===== 请求 =====
class LoginRequest(BaseModel):
    username: str
    password: str


# ===== 响应 =====
class UserInfo(BaseModel):
    """HR 用户信息"""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None


class TokenResponse(BaseModel):
    """登录 / 刷新返回的 token"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 86400  # 24h
    user: UserInfo