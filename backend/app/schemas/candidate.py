"""
Candidate Schemas

候选人相关的请求/响应 Pydantic 模型。
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ===== 响应 =====
class CandidateOut(BaseModel):
    """候选人详情"""
    id: str
    position_id: int
    name: str
    email: str
    resume_type: int  # 0=PDF / 1=Word
    parse_status: int  # 0=待解析 / 1=解析中 / 2=成功 / 3=失败
    parse_error: Optional[str] = None
    is_scanned_document: bool = False
    uploaded_at: int
    created_at: int

    model_config = ConfigDict(from_attributes=True)


class CandidateCreateResponse(BaseModel):
    """上传候选人简历后立即返回"""
    candidate_id: str
    parse_status: str = "parsing"  # 人类可读


class CandidateListResponse(BaseModel):
    items: list[CandidateOut]
    total: int
    page: int
    page_size: int


class ResumeTextResponse(BaseModel):
    """候选人解析后的简历文本（仅用于详情查看，不进列表）"""
    candidate_id: str
    parse_status: int  # 0=待解析 / 1=解析中 / 2=成功 / 3=失败
    parse_error: Optional[str] = None
    resume_text: Optional[str] = None  # 失败时为 None
    is_scanned_document: Optional[bool] = None
    parsed_at: Optional[int] = None
    resume_type: int  # 0=PDF / 1=Word

    model_config = ConfigDict(from_attributes=True)