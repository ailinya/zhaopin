"""
统一 API 响应封装（§16.1 借鉴 GraphRAGAgent）

所有 endpoint 都返回 APIResponse[T]，前端统一处理：
- code == 0  → 成功，从 data 取数据
- code != 0  → 错误，msg 展示给用户

包含 request_id 用于链路追踪。
"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

import uuid

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应"""

    code: int = Field(default=0, description="0=成功，非0=错误码")
    msg: str = Field(default="success", description="响应消息")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="请求 ID（链路追踪）")
    data: T | None = Field(default=None, description="响应数据")

    @classmethod
    def ok(cls, data: T | None = None, msg: str = "success") -> "APIResponse[T]":
        """成功响应"""
        return cls(code=0, msg=msg, data=data)

    @classmethod
    def err(cls, code: int, msg: str, data: Any | None = None) -> "APIResponse":
        """错误响应"""
        return cls(code=code, msg=msg, data=data)

    @property
    def is_success(self) -> bool:
        return self.code == 0


# ===== 错误码常量（与 core/errors.py 中的 ErrorCode 保持一致）=====
# 这里只放一些常用的快捷常量，避免 import 循环
class CommonCode:
    SUCCESS = 0
    INTERNAL_ERROR = 5000
    PARAM_MISSING = 1001
    UNAUTHORIZED = 4001  # 通用未授权
    FORBIDDEN = 4003