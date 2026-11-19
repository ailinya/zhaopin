"""
PDF 报告渲染服务（Day 2）

Jinja2 模板 + WeasyPrint 转 PDF：
- render_report_pdf(candidate_name, position, interviewer, evaluation) → bytes

WeasyPrint 是同步阻塞的（CPU bound），调用方应在 executor 里跑。
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


logger = logging.getLogger(__name__)


# ===== Jinja2 环境 =====
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


# ===== 辅助函数 =====

def _score_class(score: int) -> str:
    """根据分数返回 CSS class（高/中/低）"""
    if score >= 80:
        return "high"
    elif score >= 60:
        return "mid"
    return "low"


def _recommendation_class(recommendation: str) -> str:
    """根据录用建议返回 CSS class"""
    if "推荐" in recommendation:
        return "rec-positive"
    elif "考虑" in recommendation:
        return "rec-neutral"
    return "rec-negative"


def _prepare_question_evaluations(question_evaluations: list) -> list[dict]:
    """为每个问题加上 score_class"""
    result = []
    for q in question_evaluations:
        if hasattr(q, "model_dump"):
            base = q.model_dump()
        else:
            base = dict(q)
        # 兼容 dict / pydantic 两种：score 可以是属性或键
        score = base.get("score") if isinstance(base, dict) else getattr(q, "score", 0)
        base["score_class"] = _score_class(score * 10)  # 0-10 → 0-100
        result.append(base)
    return result


# ===== 主函数 =====

def render_report_pdf(
    candidate_name: str,
    position: str,
    interviewer: str,
    evaluation: Any,
    question_count: int = 0,
) -> bytes:
    """
    渲染 PDF 报告

    Args:
        candidate_name: 候选人姓名
        position: 应聘岗位
        interviewer: 面试官
        evaluation: ReportEvaluation（Pydantic schema 或 dict）
        question_count: 题目数量

    Returns:
        PDF 二进制内容
    """
    # 准备模板数据
    if hasattr(evaluation, "model_dump"):
        eval_data = evaluation.model_dump()
    else:
        eval_data = dict(evaluation)

    template_data = {
        "interview_date": datetime.now().strftime("%Y-%m-%d"),
        "candidate_name": candidate_name,
        "position": position,
        "interviewer": interviewer,
        "question_count": question_count or len(eval_data.get("question_evaluations", [])),
        "technical_score": eval_data.get("technical_score", 0),
        "communication_score": eval_data.get("communication_score", 0),
        "overall_score": eval_data.get("overall_score", 0),
        "technical_class": _score_class(eval_data.get("technical_score", 0)),
        "communication_class": _score_class(eval_data.get("communication_score", 0)),
        "overall_class": _score_class(eval_data.get("overall_score", 0)),
        "comments": eval_data.get("comments", ""),
        "recommendation": eval_data.get("recommendation", ""),
        "recommendation_class": _recommendation_class(eval_data.get("recommendation", "")),
        "question_evaluations": _prepare_question_evaluations(
            eval_data.get("question_evaluations", [])
        ),
    }

    # 渲染 HTML
    template = _jinja_env.get_template("report.html")
    html_content = template.render(**template_data)

    # HTML → PDF
    return _html_to_pdf(html_content)


def _html_to_pdf(html_content: str) -> bytes:
    """HTML → PDF（WeasyPrint）"""
    try:
        from weasyprint import HTML
    except ImportError:
        logger.error("weasyprint_not_installed")
        raise

    # WeasyPrint 是同步阻塞调用（CPU bound）
    html = HTML(string=html_content, base_url=str(_TEMPLATES_DIR))
    pdf_bytes = html.write_pdf()
    return pdf_bytes


async def render_report_pdf_async(
    candidate_name: str,
    position: str,
    interviewer: str,
    evaluation: Any,
    question_count: int = 0,
) -> bytes:
    """
    异步版本（实际跑在线程池里）

    用法：
        pdf_bytes = await report_renderer.render_report_pdf_async(...)
    """
    from functools import partial
    from app.core.main_loop import get_main_loop
    import asyncio

    loop = get_main_loop()
    return await loop.run_in_executor(
        None,
        partial(render_report_pdf, candidate_name, position, interviewer, evaluation, question_count),
    )