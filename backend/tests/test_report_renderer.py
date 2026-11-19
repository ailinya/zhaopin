"""
PDF 报告渲染测试
"""
import pytest
from pydantic import BaseModel

from app.services.report_renderer import (
    render_report_pdf,
    _score_class,
    _recommendation_class,
)


# ===== Mock 数据 =====

class MockQuestionEval(BaseModel):
    id: int
    question: str
    score_standard: str
    answer: str
    score: int
    comments: str


class MockReportEvaluation(BaseModel):
    question_evaluations: list[MockQuestionEval]
    technical_score: int
    communication_score: int
    overall_score: int
    comments: str
    recommendation: str


@pytest.fixture
def sample_evaluation():
    return MockReportEvaluation(
        question_evaluations=[
            MockQuestionEval(
                id=1, question="Test Q1", score_standard="Standard 1",
                answer="Answer 1", score=8, comments="Good",
            ),
            MockQuestionEval(
                id=2, question="Test Q2", score_standard="Standard 2",
                answer="Answer 2", score=6, comments="OK",
            ),
        ],
        technical_score=82,
        communication_score=78,
        overall_score=80,
        comments="Candidate showed solid skills.",
        recommendation="推荐录用",
    )


# ===== 单元测试 =====

def test_score_class_high():
    assert _score_class(85) == "high"
    assert _score_class(80) == "high"

def test_score_class_mid():
    assert _score_class(70) == "mid"
    assert _score_class(60) == "mid"

def test_score_class_low():
    assert _score_class(50) == "low"
    assert _score_class(0) == "low"


def test_recommendation_class_positive():
    assert _recommendation_class("推荐录用") == "rec-positive"
    assert _recommendation_class("强烈推荐") == "rec-positive"

def test_recommendation_class_neutral():
    assert _recommendation_class("可以考虑") == "rec-neutral"

def test_recommendation_class_negative():
    assert _recommendation_class("不建议录用") == "rec-negative"


def test_render_report_pdf_returns_bytes(sample_evaluation):
    """渲染 PDF 返回 bytes"""
    try:
        pdf_bytes = render_report_pdf(
            candidate_name="张三",
            position="Backend Engineer",
            interviewer="Tech Lead",
            evaluation=sample_evaluation,
            question_count=2,
        )
    except (ImportError, OSError):
        pytest.skip("weasyprint 未安装或系统缺 GTK3")

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes[:5] == b"%PDF-"


def test_render_report_pdf_with_dict_evaluation(sample_evaluation):
    """支持 dict 类型的 evaluation（兼容）"""
    try:
        pdf_bytes = render_report_pdf(
            candidate_name="李四",
            position="Frontend Engineer",
            interviewer="Manager",
            evaluation=sample_evaluation.model_dump(),
            question_count=2,
        )
    except (ImportError, OSError):
        pytest.skip("weasyprint 未安装或系统缺 GTK3")

    assert pdf_bytes[:5] == b"%PDF-"


def test_render_report_pdf_handles_empty_questions():
    """空题目也能渲染"""
    try:
        pdf_bytes = render_report_pdf(
            candidate_name="Test",
            position="Test",
            interviewer="Test",
            evaluation=MockReportEvaluation(
                question_evaluations=[],
                technical_score=0,
                communication_score=0,
                overall_score=0,
                comments="",
                recommendation="可以考虑",
            ),
            question_count=0,
        )
    except (ImportError, OSError):
        pytest.skip("weasyprint 未安装或系统缺 GTK3")

    assert pdf_bytes[:5] == b"%PDF-"