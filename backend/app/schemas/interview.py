"""
Interview Schemas

HR 端面试 CRUD 的请求/响应 Pydantic 模型。
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ===== 请求 =====
class InterviewCreate(BaseModel):
    candidate_id: str
    position_id: Optional[int] = None
    interviewer: Optional[str] = None
    start_time: Optional[int] = None
    is_passed: Optional[int] = 0


class InterviewUpdate(BaseModel):
    interviewer: Optional[str] = None
    start_time: Optional[int] = None
    is_passed: Optional[int] = None
    status: Optional[int] = None


# ===== 响应 =====
class InterviewOut(BaseModel):
    id: int
    candidate_id: str
    position_id: int
    interviewer: Optional[str]
    start_time: int
    end_time: Optional[int]
    status: int
    question_count: Optional[int]
    answered_count: int
    total_hard_questions: int
    total_medium_questions: int
    total_easy_questions: int
    is_passed: Optional[int]
    voice_reading: int
    token: str
    langgraph_thread_id: str
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


class InterviewCreateResponse(BaseModel):
    """创建面试后立即返回（含 token 供候选人 URL）"""
    id: int
    token: str
    status: int


class InterviewListResponse(BaseModel):
    items: list[InterviewOut]
    total: int
    page: int
    page_size: int