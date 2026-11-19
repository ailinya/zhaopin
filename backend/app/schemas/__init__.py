"""
Pydantic Schemas 集中导出（按域拆分）

按域拆为多个文件：
- common.py: 公共 schemas（StatusResponse, ErrorResponse）
- auth.py: 登录/Token/UserInfo
- position.py: 岗位 CRUD
- candidate.py: 候选人管理
- interview.py: HR 端面试 CRUD
- portal.py: 候选人 portal（token URL 鉴权）
- llm.py: LLM 输出 schema（QuestionList, ReportEvaluation）
"""
from app.schemas.response import APIResponse
from app.schemas.common import StatusResponse, ErrorResponse
from app.schemas.auth import LoginRequest, UserInfo, TokenResponse
from app.schemas.position import (
    PositionCreate, PositionUpdate, PositionOut, PositionListResponse,
)
from app.schemas.candidate import (
    CandidateOut, CandidateCreateResponse, CandidateListResponse,
)
from app.schemas.interview import (
    InterviewCreate, InterviewUpdate, InterviewOut,
    InterviewCreateResponse, InterviewListResponse,
)
from app.schemas.portal import (
    CandidateInterviewInfo, QuestionOut, SubmitAnswerResponse,
    VoiceReadingToggle, VoiceReadingResponse,
)
from app.schemas.llm import (
    QuestionItem, QuestionList, QuestionEvaluation, ReportEvaluation,
)

__all__ = [
    "APIResponse",
    # Common
    "StatusResponse", "ErrorResponse",
    # Auth
    "LoginRequest", "UserInfo", "TokenResponse",
    # Position
    "PositionCreate", "PositionUpdate", "PositionOut", "PositionListResponse",
    # Candidate
    "CandidateOut", "CandidateCreateResponse", "CandidateListResponse",
    # Interview
    "InterviewCreate", "InterviewUpdate", "InterviewOut",
    "InterviewCreateResponse", "InterviewListResponse",
    # Portal
    "CandidateInterviewInfo", "QuestionOut", "SubmitAnswerResponse",
    "VoiceReadingToggle", "VoiceReadingResponse",
    # LLM
    "QuestionItem", "QuestionList", "QuestionEvaluation", "ReportEvaluation",
]