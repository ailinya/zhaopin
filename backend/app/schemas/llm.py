"""
LLM 输出的 Pydantic Schemas

用于 chat_json() 校验 LLM 输出结构：
- QuestionList：10 道面试题
- ReportEvaluation：面试评估报告（含 per-question + 总分）
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ===== 出题 =====

class QuestionItem(BaseModel):
    """单道面试题"""
    question: str = Field(..., min_length=5, description="题目内容")
    score_standard: str = Field(..., min_length=3, description="评分标准")
    difficulty: Literal["hard", "medium", "easy"] = Field(
        default="medium", description="难度"
    )


class QuestionList(BaseModel):
    """10 道面试题的列表"""
    questions: list[QuestionItem] = Field(..., min_length=10, max_length=10)


# ===== 评估 =====

class QuestionEvaluation(BaseModel):
    """单题评估"""
    id: int = Field(..., description="题目 ID")
    question: str
    score_standard: str
    answer: str
    score: int = Field(..., ge=0, le=10, description="0-10 分")
    comments: str


def _coerce_int(v):
    """LLM 偶发返回 55.5 这种小数，转 int 容错"""
    if v is None:
        return v
    if isinstance(v, float):
        return int(round(v))
    if isinstance(v, str):
        try:
            return int(round(float(v)))
        except (ValueError, TypeError):
            return v
    return v


class ReportEvaluation(BaseModel):
    """完整面试评估报告"""
    model_config = {"arbitrary_types_allowed": True}

    question_evaluations: list[QuestionEvaluation] = Field(default_factory=list)
    # 用 field_validator 把 LLM 偶发的小数（55.5）转 int，避免整次评估失败
    technical_score: int = Field(..., ge=0, le=100, description="技术能力 0-100")
    communication_score: int = Field(..., ge=0, le=100, description="沟通能力 0-100")
    overall_score: int = Field(..., ge=0, le=100, description="综合评分 0-100")
    comments: str = Field(..., min_length=10, description="综合评语")
    # recommendation 有默认值，LLM 漏返时不会整次失败
    recommendation: str = Field(
        default="（模型未给出建议）",
        description="录用建议（自由文本）",
    )

    @field_validator("technical_score", "communication_score", "overall_score", mode="before")
    @classmethod
    def _coerce_scores(cls, v):
        return _coerce_int(v)

    @field_validator("recommendation", mode="after")
    @classmethod
    def _fallback_recommendation(cls, v, info):
        """如果 LLM 没填或填了默认值，根据 overall_score 自动推导"""
        if v and v.strip() and v != "（模型未给出建议）":
            return v
        overall = info.data.get("overall_score", 0) if hasattr(info, "data") else 0
        if overall >= 80:
            return "推荐录用"
        if overall >= 60:
            return "可以考虑"
        return "不建议录用"