"""
4 个 LangGraph 节点（§10.4 + Day 3 DI 重构）

节点签名：`node(state, *, deps)` - 通过 deps 接收所有依赖
节点内不再 import app.database / app.services.sse_manager 等
这样测试可以注入 mock deps。
"""
import asyncio
import logging
from typing import Any

from langgraph.types import interrupt

from app.core.logging import get_logger
from app.schemas.llm import QuestionList, ReportEvaluation
from app.workflow.dependencies import WorkflowDeps


logger = get_logger(__name__)


# ===== 节点 A：生成面试题 =====

def generate_questions_node(state: dict, *, deps: WorkflowDeps) -> dict:
    """
    节点 A：调 LLM 生成 10 道题，写入 DB，推 SSE 进度
    """
    interview_id = state["interview_id"]

    interview = deps.interview_repo.get(interview_id)
    if not interview:
        return {"error": f"interview {interview_id} not found", "error_node": "generate_questions"}

    candidate = deps.candidate_repo.get(interview.candidate_id)
    position = deps.position_repo.get(interview.position_id)

    if not candidate or not position:
        return {"error": "candidate or position not found", "error_node": "generate_questions"}

    # 推 SSE（best-effort，不阻塞节点）
    _publish_sse(deps, interview_id, {
        "event": "questions_generating",
        "data": {"interview_id": interview_id, "progress": 0.1},
    })

    # 渲染 prompt
    prompt = deps.prompt_renderer(
        "question_generation.v1.j2",
        position_name=position.name,
        position_requirements=position.requirements or "",
        position_responsibilities=position.responsibilities or "",
        resume_text=candidate.resume_text or "（简历为空，基于岗位 JD 出题）",
    )

    # 调 LLM（懒导入，便于 patch）
    from app.services.llm_service import chat_json
    try:
        result: QuestionList = chat_json(
            [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ],
            schema=QuestionList,
        )
    except Exception as e:
        logger.error("llm_question_generation_failed", exc_msg=str(e))
        return {"error": f"LLM 调用失败: {e}", "error_node": "generate_questions"}

    # 写 DB
    questions = deps.question_repo.bulk_create(
        interview_id,
        [q.model_dump() for q in result.questions],
    )

    # 统计难度分布
    dist = {"hard": 0, "medium": 0, "easy": 0}
    for q in result.questions:
        dist[q.difficulty] = dist.get(q.difficulty, 0) + 1

    # 更新 interview
    deps.interview_repo.update_questions_generated(
        interview_id,
        question_count=len(questions),
        difficulty_distribution=dist,
    )

    # 推 SSE
    _publish_sse(deps, interview_id, {
        "event": "questions_generated",
        "data": {
            "interview_id": interview_id,
            "count": len(questions),
            "difficulty_distribution": dist,
        },
    })

    # Audit
    deps.audit_repo.create(
        event_type="questions_generated",
        actor_id="system",
        actor_type="system",
        interview_id=interview_id,
        metadata={"count": len(questions), "difficulty": dist},
    )

    deps.db.commit()

    return {
        # 用纯字段构造 dict，避开 SQLAlchemy 的 _sa_instance_state（msgpack 不能序列化）
        "questions": [
            {
                "id": q.id,
                "question": q.question,
                "difficulty": q.difficulty,
                "score_standard": q.score_standard,
            }
            for q in questions
        ],
        "question_count": len(questions),
        "difficulty_distribution": dist,
    }


# ===== 节点 B：等待候选人（interrupt）=====

def wait_for_candidate_node(state: dict, *, deps: WorkflowDeps) -> dict:
    """
    节点 B：interrupt 等待候选人答完所有题
    """
    interview_id = state["interview_id"]
    pending = state.get("pending_question_ids") or [q["id"] for q in state.get("questions", [])]

    # 阻塞点：等候选人答完
    resume_payload = interrupt({
        "interview_id": interview_id,
        "pending_question_ids": pending,
        "total_count": state.get("question_count", len(pending)),
        "message": f"等待候选人答完 {len(pending)} 道题",
    })

    return {
        "answered_count": resume_payload.get("answered_count", 0),
        "pending_question_ids": [],
    }


# ===== 节点 C：校验完整性 =====

def validate_complete_node(state: dict, *, deps: WorkflowDeps) -> dict:
    """
    节点 C：查 DB 实际答题数（防止 race condition）
    """
    interview_id = state["interview_id"]
    total = deps.question_repo.count_by_interview(interview_id)
    answered = deps.question_repo.count_answered(interview_id)

    if answered < total:
        # 重复触发或漏题，重新挂起
        pending = deps.question_repo.list_unanswered(interview_id)
        resume_payload = interrupt({
            "interview_id": interview_id,
            "pending_question_ids": [q.id for q in pending],
            "total_count": total,
            "message": f"还有 {total - answered} 道题未答完",
        })
        return {
            "answered_count": resume_payload.get("answered_count", answered),
            "pending_question_ids": [],
        }

    return {"answered_count": answered}


# ===== 节点 D：生成评估报告 =====

def generate_report_node(state: dict, *, deps: WorkflowDeps) -> dict:
    """
    节点 D：调 LLM 评估，生成 PDF，写 DB
    """
    interview_id = state["interview_id"]

    interview = deps.interview_repo.get(interview_id)
    if not interview:
        return {"error": "interview not found", "error_node": "generate_report"}

    candidate = deps.candidate_repo.get(interview.candidate_id)
    position = deps.position_repo.get(interview.position_id)
    questions = deps.question_repo.list_by_interview(interview_id)

    # 推 SSE
    _publish_sse(deps, interview_id, {
        "event": "report_generating",
        "data": {"interview_id": interview_id},
    })

    # 准备问答数据
    qa_data = [
        {
            "question": q.question,
            "score_standard": q.score_standard or "",
            "answer": q.answer_text or "（未回答）",
        }
        for q in questions
    ]

    # 渲染 prompt
    prompt = deps.prompt_renderer(
        "report_evaluation.v1.j2",
        candidate_name=candidate.name if candidate else "未知",
        position_name=position.name if position else "未知",
        interviewer=interview.interviewer or "面试官",
        questions=qa_data,
    )

    # 调 LLM
    from app.services.llm_service import chat_json
    try:
        result: ReportEvaluation = chat_json(
            [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ],
            schema=ReportEvaluation,
        )
    except Exception as e:
        logger.error("llm_report_generation_failed", exc_msg=str(e))
        return {"error": f"LLM 调用失败: {e}", "error_node": "generate_report"}

    # 渲染 PDF
    from app.services.report_renderer import render_report_pdf
    pdf_bytes = render_report_pdf(
        candidate_name=candidate.name if candidate else "未知",
        position=position.name if position else "未知",
        interviewer=interview.interviewer or "面试官",
        evaluation=result,
        question_count=len(questions),
    )

    # 保存报告
    report_path = deps.file_storage.save_report(interview_id, pdf_bytes)

    # 更新 DB
    is_passed = 1 if result.overall_score >= 60 else 0
    deps.interview_repo.update_report(
        interview_id,
        report_path=str(report_path),
        is_passed=is_passed,
    )

    # 推 SSE
    _publish_sse(deps, interview_id, {
        "event": "report_ready",
        "data": {
            "interview_id": interview_id,
            "report_id": interview_id,
            "download_url": f"/api/interviews/{interview_id}/report",
        },
    })

    # Audit
    deps.audit_repo.create(
        event_type="report_generated",
        actor_id="system",
        actor_type="system",
        interview_id=interview_id,
        metadata={"overall_score": result.overall_score, "is_passed": is_passed},
    )

    deps.db.commit()

    return {
        "report_id": interview_id,
        "report_path": str(report_path),
    }


# ===== 工具函数 =====

def _publish_sse(deps: WorkflowDeps, interview_id: int, event: dict) -> None:
    """Best-effort SSE 推送（失败不阻塞节点）"""
    try:
        from app.core.main_loop import get_main_loop
        loop = get_main_loop()
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                deps.sse_manager.publish(interview_id, event),
                loop,
            )
        else:
            # 没有 event loop（不应该发生），用 asyncio.run
            asyncio.run(deps.sse_manager.publish(interview_id, event))
    except Exception as e:
        logger.warning("sse_publish_failed", exc_msg=str(e))