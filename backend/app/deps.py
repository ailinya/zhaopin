"""
FastAPI 依赖注入（§14）

依赖：
- get_db: 数据库 Session
- get_current_user: HR 端 JWT 鉴权
- get_current_candidate: 候选人端 token URL 鉴权
- get_sse_manager: SSE Manager 单例
"""
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.errors import APIError, ErrorCode
from app.core.security import decode_token
from app.database import get_db as _get_db
from app.models.user import User, UserRepository
from app.models.interview import Interview, InterviewRepository
from app.services.sse_manager import SSEManager, get_sse_manager as _get_sse_manager


# ===== 数据库 =====
def get_db() -> Session:
    """数据库 Session 依赖"""
    yield from _get_db()


# ===== 鉴权 =====
def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """HR 端鉴权依赖：解析 Bearer Token，返回当前用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise APIError.unauthorized(
            ErrorCode.UNAUTHORIZED,
            "缺少 Authorization header 或格式错误",
        )

    token = authorization[7:]  # 去掉 "Bearer "
    try:
        payload = decode_token(token, expected_type="access")
    except Exception:
        raise APIError.unauthorized(
            ErrorCode.TOKEN_EXPIRED,
            "Token 无效或已过期",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise APIError.unauthorized(
            ErrorCode.UNAUTHORIZED,
            "Token payload 缺少 sub",
        )

    user = UserRepository(db).get(user_id)
    if not user:
        raise APIError.unauthorized(
            ErrorCode.USER_NOT_FOUND,
            f"用户 {user_id} 不存在",
        )

    if not user.is_active:
        raise APIError.forbidden(
            ErrorCode.USER_DISABLED,
            "账号已停用",
        )

    return user


def get_optional_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """可选的 HR 用户（用于部分公开端点，如未登录也能访问的资源）"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        return get_current_user(authorization, db)
    except APIError:
        return None


def get_current_candidate(
    token: str,
    db: Session = Depends(get_db),
) -> Interview:
    """候选人端鉴权：通过 URL token 解析面试"""
    if not token or not token.strip():
        raise APIError.bad_request(
            ErrorCode.PARAM_MISSING,
            "缺少 token 参数",
        )

    interview = InterviewRepository(db).get_by_token(token)
    if not interview:
        raise APIError.not_found(
            ErrorCode.INTERVIEW_NOT_FOUND,
            "面试链接无效或已过期",
        )

    return interview


# ===== SSE =====
def get_sse_manager_dep() -> SSEManager:
    """SSE Manager 依赖（FastAPI 用）"""
    return _get_sse_manager()