"""
Candidate Portal Schemas

候选人端（不需要 JWT，用 token URL 鉴权）相关 Pydantic 模型。
"""
from pydantic import BaseModel


# ===== 响应 =====
class CandidateInterviewInfo(BaseModel):
    """候选人获取面试信息"""
    interview_id: int
    candidate_name: str
    position_name: str
    time: str  # 格式化后的字符串
    status: int
    question_count: int
    answered_count: int = 0
    voice_reading: bool


class QuestionOut(BaseModel):
    """单道题"""
    id: int
    text: str


class SubmitAnswerResponse(BaseModel):
    """提交答案响应"""
    status: str = "audio_received"
    transcription_pending: bool = True
    answered_count: int = 0
    next_question: QuestionOut


# ===== 请求 =====
class VoiceReadingToggle(BaseModel):
    """切换语音朗读设置请求"""
    enabled: bool


class VoiceReadingResponse(BaseModel):
    """语音朗读设置响应"""
    voice_reading: bool