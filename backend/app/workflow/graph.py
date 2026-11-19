"""
LangGraph StateGraph 组装（§10.5 + Day 3 DI 改造）

每个节点用 lambda 包装，注入 deps 参数：
    builder.add_node("generate_questions", lambda s: generate_questions_node(s, deps=deps))

测试时：build_graph_with_deps(mock_deps) - deps 全部可替换
生产时：build_graph_with_deps(build_deps_from_db(db)) - 用真实 DB
"""
from functools import partial
from typing import Optional

from langgraph.graph import StateGraph, START, END

from app.workflow.state import InterviewState
from app.workflow.nodes import (
    generate_questions_node,
    wait_for_candidate_node,
    validate_complete_node,
    generate_report_node,
)
from app.workflow.dependencies import WorkflowDeps, build_deps_from_db
from app.workflow.checkpointer import get_checkpointer_sync


# ===== 单例 compiled graph（生产环境用） =====
_compiled_graph = None
_cached_deps: Optional[WorkflowDeps] = None


def build_graph_with_deps(deps: WorkflowDeps) -> StateGraph:
    """
    用 deps 构建图（节点通过 lambda 闭包拿到 deps）

    测试用法：
        deps = WorkflowDeps(db=mock_db, ...)
        graph = build_graph_with_deps(deps)
    生产用法：
        deps = build_deps_from_db(real_db)
        graph = build_graph_with_deps(deps)
    """
    builder = StateGraph(InterviewState)

    # 节点用 partial 注入 deps
    builder.add_node("generate_questions", partial(generate_questions_node, deps=deps))
    builder.add_node("wait_for_candidate", partial(wait_for_candidate_node, deps=deps))
    builder.add_node("validate_complete", partial(validate_complete_node, deps=deps))
    builder.add_node("generate_report", partial(generate_report_node, deps=deps))

    # 边（线性流）
    builder.add_edge(START, "generate_questions")
    builder.add_edge("generate_questions", "wait_for_candidate")
    builder.add_edge("wait_for_candidate", "validate_complete")
    builder.add_edge("validate_complete", "generate_report")
    builder.add_edge("generate_report", END)

    return builder


def get_compiled_graph():
    """获取编译后的图（单例，Week 1 兼容入口）"""
    global _compiled_graph, _cached_deps
    if _compiled_graph is None:
        from app.database import SessionLocal
        db = SessionLocal()
        _cached_deps = build_deps_from_db(db)
        builder = build_graph_with_deps(_cached_deps)
        _compiled_graph = builder.compile(checkpointer=get_checkpointer_sync())
    return _compiled_graph


def reset_compiled_graph():
    """重置单例（测试用）"""
    global _compiled_graph, _cached_deps
    if _cached_deps:
        _cached_deps.close()
    _compiled_graph = None
    _cached_deps = None


def run_workflow_sync(
    interview_id: int,
    thread_id: str,
    initial_state: dict,
    deps: Optional[WorkflowDeps] = None,
) -> dict:
    """
    同步启动工作流

    Args:
        deps: 如果为 None，用 build_deps_from_db() 创建生产 deps；
              测试时传 mock deps
    """
    if deps is None:
        from app.database import SessionLocal
        db = SessionLocal()
        deps = build_deps_from_db(db)

    builder = build_graph_with_deps(deps)
    graph = builder.compile(checkpointer=get_checkpointer_sync())
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(initial_state, config)


def resume_workflow(thread_id: str, resume_payload: dict) -> dict:
    """从 interrupt 恢复工作流（用单例 graph）"""
    from langgraph.types import Command
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(Command(resume=resume_payload), config)


def get_workflow_state(thread_id: str):
    """查询当前 workflow state"""
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": thread_id}}
    return graph.get_state(config)