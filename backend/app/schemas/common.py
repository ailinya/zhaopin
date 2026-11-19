"""
公共 Schemas

跨多个域复用的 Pydantic 模型。
"""
from pydantic import BaseModel


class StatusResponse(BaseModel):
    """通用 status 响应（如 {"status": "success"}）"""
    status: str = "success"


class ErrorResponse(BaseModel):
    """错误响应（备选，大部分情况用 APIResponse 包装）"""
    code: int
    msg: str
    data: dict = {}