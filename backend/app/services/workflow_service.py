"""
Workflow 服务（§10）

- run_for_interview()：创建面试后异步启动 LangGraph
- resume_after_completion()：候选人答完最后一题时触发
- get_status()：查 workflow state（HR 后台 / 巡检）
- render_prompt()：Jinja2 模板渲染（system + user 拆分）
- render_simple_pdf()：简化版 PDF 渲染（Week 3 接入 WeasyPrint）
"""
import asyncio
import logging
import threading
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


logger = logging.getLogger(__name__)


# ===== Jinja2 环境 =====
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_prompt(template_name: str, **kwargs) -> dict:
    """
    渲染 prompt 模板，返回 {"system": "...", "user": "..."}

    约定：模板文件以 '# system' 开头为 system prompt，其余为 user prompt
    """
    template_text = (_PROMPTS_DIR / template_name).read_text(encoding="utf-8")

    # 简单按 '# system' 分割
    if "# system" in template_text:
        system_part, user_part = template_text.split("# system", 1)
        # system_part 是 # system 之前的内容（通常是注释）
        system_text = system_part.strip()
        user_text = _render_jinja(user_part, **kwargs)
    else:
        system_text = ""
        user_text = _render_jinja(template_text, **kwargs)

    return {"system": system_text, "user": user_text}


def _render_jinja(template_text: str, **kwargs) -> str:
    """用 Jinja2 渲染模板"""
    from jinja2 import Template
    template = Template(template_text)
    return template.render(**kwargs)


# ===== 简单 PDF 渲染（Week 3 接入 WeasyPrint）=====

def render_simple_pdf(
    candidate_name: str,
    position_name: str,
    evaluation: Any,
) -> bytes:
    """
    委托给 report_renderer（Day 2 升级到 WeasyPrint）
    """
    from app.services.report_renderer import render_report_pdf
    return render_report_pdf(
        candidate_name=candidate_name,
        position=position_name,
        interviewer=evaluation.interviewer if hasattr(evaluation, "interviewer") else "面试官",
        evaluation=evaluation,
    )


# ===== Workflow 启动 / 恢复 =====

def run_for_interview(interview_id: int, thread_id: str) -> None:
    """
    启动工作流（创建面试后异步调用）

    在后台线程跑 workflow，不阻塞 API。
    服务重启后，scheduler 巡检可从 checkpoint 恢复（§10.7）。
    """
    from app.workflow.graph import run_workflow_sync
    from app.database import SessionLocal
    from app.models import (
        InterviewRepository, CandidateRepository, PositionRepository,
    )

    def _run():
        session = SessionLocal()
        try:
            interview = InterviewRepository(session).get(interview_id)
            if not interview:
                logger.error(f"interview {interview_id} not found")
                return
            candidate = CandidateRepository(session).get(interview.candidate_id)
            position = PositionRepository(session).get(interview.position_id)

            if not candidate or not position:
                logger.error(f"interview {interview_id}: candidate or position missing")
                return

            initial_state = {
                "interview_id": interview_id,
                "langgraph_thread_id": thread_id,
                "candidate_id": interview.candidate_id,
                "position_id": interview.position_id,
                "resume_text": candidate.resume_text or "",
                "position_name": position.name,
                "position_requirements": position.requirements or "",
                "position_responsibilities": position.responsibilities or "",
                "questions": [],
                "question_count": 0,
                "difficulty_distribution": {},
                "answered_count": 0,
                "pending_question_ids": [],
                "report_id": None,
                "report_path": None,
                "error": None,
                "error_node": None,
            }

            logger.info(f"workflow_starting interview_id={interview_id}")
            try:
                result = run_workflow_sync(interview_id, thread_id, initial_state)
                logger.info(f"workflow_finished interview_id={interview_id}, result_keys={list(result.keys()) if result else 'None'}")
            except Exception as e:
                import traceback
                logger.error(f"workflow_failed interview_id={interview_id} exc={e}, traceback={traceback.format_exc()}")
        finally:
            session.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def resume_after_completion(thread_id: str, answered_count: int) -> None:
    """
    候选人答完最后一题后触发 resume（api/candidate_portal.py 调用）

    同步执行 resume（wait_for_candidate_node 会立即返回并继续到节点 D）
    """
    from app.workflow.graph import resume_workflow
    import asyncio

    async def _resume():
        try:
            resume_workflow(thread_id, {"answered_count": answered_count})
        except Exception as e:
            logger.error(f"workflow_resume_failed thread_id={thread_id} exc={e}")

    # 在后台线程跑（不阻塞 submit_answer API）
    def _run_async():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_resume())
            loop.close()
        except Exception as e:
            logger.error(f"workflow_resume_thread_failed exc={e}")

    thread = threading.Thread(target=_run_async, daemon=True)
    thread.start()


def get_status(interview_id: int) -> dict | None:
    """
    查询 workflow 状态（HR 后台实时进度条用）

    Returns:
        None if not found, else dict with current state snapshot
    """
    from app.workflow.graph import get_workflow_state
    from app.database import InterviewRepository
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        interview = InterviewRepository(session).get(interview_id)
        if not interview or not interview.langgraph_thread_id:
            return None
        state_snapshot = get_workflow_state(interview.langgraph_thread_id)
        if not state_snapshot:
            return None
        return {
            "status": interview.status,
            "question_count": interview.question_count,
            "answered_count": interview.answered_count,
            "next_node": str(state_snapshot.next) if state_snapshot.next else None,
        }
    finally:
        session.close()