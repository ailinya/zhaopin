"""
Position Schemas

岗位（HR 创建）相关的请求/响应 Pydantic 模型。
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ===== 基础 =====
class PositionBase(BaseModel):
    name: str
    requirements: str = ""
    responsibilities: str = ""
    quantity: int = 1
    status: int = 0  # 0=未启动 / 1=进行中 / 2=已完成
    recruiter: Optional[str] = None


# ===== 请求 =====
class PositionCreate(PositionBase):
    pass


class PositionUpdate(BaseModel):
    name: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    quantity: Optional[int] = None
    status: Optional[int] = None
    recruiter: Optional[str] = None


# ===== 响应 =====
class PositionOut(PositionBase):
    id: int
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


class PositionListResponse(BaseModel):
    items: list[PositionOut]
    total: int
    page: int
    page_size: int