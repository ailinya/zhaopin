"""
Auth API（§14）

端点：
- POST /api/auth/login
- POST /api/auth/refresh
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.errors import APIError, ErrorCode
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.deps import get_db
from app.models.user import UserRepository
from app.models.audit_log import AuditLogRepository
from app.schemas.response import APIResponse


router = APIRouter(prefix="/api/auth", tags=["auth"])


# ===== Schemas =====
class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: str
    username: str
    email: str
    full_name: str | None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 86400  # 24h
    user: UserInfo


# ===== 端点 =====
@router.post("/login", response_model=APIResponse[TokenResponse])
async def login(
    req: LoginRequest,
    db: Session = Depends(get_db),
):
    """登录获取 JWT（§14.6）"""
    user_repo = UserRepository(db)
    user = user_repo.get_by_username(req.username)

    # 故意不区分"用户不存在"和"密码错"（防账号枚举）
    if not user or not verify_password(req.password, user.password_hash):
        AuditLogRepository(db).create(
            event_type="login_failed",
            actor_id=req.username,
            actor_type="user",
            metadata={"reason": "invalid_credentials"},
        )
        raise APIError.unauthorized(
            ErrorCode.INVALID_CREDENTIALS,
            "用户名或密码错误",
        )

    if not user.is_active:
        raise APIError.forbidden(
            ErrorCode.USER_DISABLED,
            "账号已停用",
        )

    # 更新最后登录时间
    user_repo.update_last_login(user.id)

    # 签发 token
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    # 审计日志
    AuditLogRepository(db).create(
        event_type="login_success",
        actor_id=user.id,
        actor_type="user",
        user_id=user.id,
        metadata={"username": user.username},
    )

    return APIResponse.ok(
        TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserInfo(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
            ),
        )
    )


@router.post("/refresh", response_model=APIResponse[TokenResponse])
async def refresh(
    refresh_token: str,
    db: Session = Depends(get_db),
):
    """用 refresh token 换新 access token（§14.6）"""
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except Exception:
        raise APIError.unauthorized(
            ErrorCode.TOKEN_EXPIRED,
            "Refresh token 无效或已过期",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise APIError.unauthorized(
            ErrorCode.UNAUTHORIZED,
            "Refresh token payload 缺少 sub",
        )

    user = UserRepository(db).get(user_id)
    if not user or not user.is_active:
        raise APIError.unauthorized(
            ErrorCode.USER_NOT_FOUND,
            "用户不存在或已停用",
        )

    # 滚动续期
    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)

    return APIResponse.ok(
        TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            user=UserInfo(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
            ),
        )
    )