"""
安全模块（§14）

包含：
- bcrypt 密码 hash/verify
- JWT 签发/解码（access + refresh）
- FastAPI 依赖（get_current_user, get_current_candidate）

Week 1 Day 4 接入。
"""
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import settings


# ===== 密码 Hash =====

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """bcrypt 加密密码"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与 hash"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


# ===== JWT =====


def create_access_token(user_id: str) -> str:
    """签发 access token（默认 24h）"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(hours=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """签发 refresh token（默认 7d）"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> dict:
    """
    解码并校验 JWT

    Raises:
        jwt.ExpiredSignatureError: token 过期
        jwt.InvalidTokenError: token 无效 / 类型不对
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )

    token_type = payload.get("type")
    if token_type != expected_type:
        raise jwt.InvalidTokenError(f"Expected token type '{expected_type}', got '{token_type}'")

    return payload


# ===== 候选人 Token =====

import secrets
import string


def generate_candidate_token(length: int | None = None) -> str:
    """生成候选人面试链接 token（默认 32 位字母数字）"""
    if length is None:
        length = settings.CANDIDATE_TOKEN_LENGTH
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))