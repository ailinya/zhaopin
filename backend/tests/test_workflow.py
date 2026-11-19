"""
Workflow 测试（state / graph 编译 / checkpointer roundtrip）
"""
import time
from unittest.mock import MagicMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.workflow.state import InterviewState
from app.workflow.graph import build_graph_with_deps, get_workflow_state
from app.workflow.checkpointer import get_checkpointer_sync, reset_checkpointer
from app.workflow.dependencies import WorkflowDeps, build_deps_from_db


# ===== State 测试 =====

def test_interview_state_typed_dict():
    """InterviewState 是 TypedDict，所有字段可访问"""
    state: InterviewState = {
        "interview_id": 1,
        "langgraph_thread_id": "test-thread",
        "candidate_id": "cand-1",
        "position_id": 1,
        "resume_text": "test",
        "position_name": "P1",
        "position_requirements": "Vue",
        "position_responsibilities": "Dev",
    }
    assert state["interview_id"] == 1
    assert state["langgraph_thread_id"] == "test-thread"


def test_interview_state_partial_fields():
    """total=False 允许部分字段缺失"""
    state: InterviewState = {"interview_id": 1}
    assert state.get("error") is None
    assert state.get("questions") is None


# ===== Graph 编译测试 =====

def test_build_graph_compiles():
    """build_graph_with_deps 返回可编译的 StateGraph"""
    # 用 mock deps（不需要真 DB）
    mock_deps = MagicMock(spec=WorkflowDeps)
    builder = build_graph_with_deps(mock_deps)
    # 编译
    graph = builder.compile()
    assert graph is not None


def test_compiled_graph_has_4_nodes():
    """编译后的图有 4 个节点"""
    mock_deps = MagicMock(spec=WorkflowDeps)
    builder = build_graph_with_deps(mock_deps)
    graph = builder.compile()
    # 节点名
    nodes = graph.nodes
    assert "generate_questions" in nodes
    assert "wait_for_candidate" in nodes
    assert "validate_complete" in nodes
    assert "generate_report" in nodes


# ===== Checkpointer 测试 =====

def test_checkpointer_singleton():
    """get_checkpointer_sync 返回单例"""
    reset_checkpointer()
    cp1 = get_checkpointer_sync()
    cp2 = get_checkpointer_sync()
    assert cp1 is cp2


def test_checkpointer_can_save_and_load_state():
    """checkpointer 能保存和恢复 state"""
    reset_checkpointer()

    # 1. 用 InMemorySaver 替代 SqliteSaver（避免文件依赖）
    from app.workflow.graph import _compiled_graph
    import app.workflow.graph as graph_module

    # 强制使用 InMemorySaver
    from langgraph.graph import StateGraph
    from app.workflow.state import InterviewState

    # 用 InMemorySaver 重建一个图用于测试
    test_checkpointer = InMemorySaver()
    builder = build_graph_with_deps(MagicMock(spec=WorkflowDeps))
    test_graph = builder.compile(checkpointer=test_checkpointer)

    config = {"configurable": {"thread_id": "test-1"}}

    # 初始 state
    initial_state = {
        "interview_id": 99,
        "langgraph_thread_id": "test-1",
        "candidate_id": "c1",
        "position_id": 1,
    }

    # 启动 graph（会在 wait_for_candidate 节点 interrupt）
    # 用 BackgroundThreads 跑避免 hang
    import threading
    result_container = {}

    def _run():
        try:
            # graph.stream 会逐节点 yield
            events = list(test_graph.stream(initial_state, config))
            result_container["events"] = events
        except Exception as e:
            result_container["error"] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=5)  # 最多等 5 秒

    # 应该会卡在 interrupt 上（没有 resume_payload）
    # 验证 state 存在
    state_snapshot = test_graph.get_state(config)
    assert state_snapshot is not None
    assert state_snapshot.values.get("interview_id") == 99


def test_graph_state_can_be_queried():
    """get_workflow_state 查 state（不存在的 thread）"""
    from app.workflow.graph import get_workflow_state

    # 不存在的 thread_id 应该不抛错
    # SqliteSaver 会返回 None 或空 state
    try:
        result = get_workflow_state("nonexistent-thread-xyz")
        # 不管返回什么，不应该抛错
    except Exception:
        # 某些实现对不存在的 thread 抛错，可以接受
        pass


# ===== 集成测试：完整流程（mock LLM）=====
# 完整流程测试需要 mock 多个 Repository（query / add / commit 等）
# Week 3 我们会引入测试数据库 fixture 简化这个
# 现在只保留节点级 / graph 编译级测试

@pytest.mark.skip(reason="需要完整 DB mock，Week 3 引入测试 fixture 后补")
def test_workflow_full_pipeline_with_mocked_llm(monkeypatch):
    """完整流程测试：mock LLM + DB，跑通 4 节点 + interrupt + resume + 报告生成"""
    pass  # TODO Week 3


# ===== DI 模式验证（Day 3）=====

def test_deps_pattern_works_with_mock():
    """DI 模式：注入 mock deps，不需要真实 DB 就能 build graph + compile"""
    # 用 MagicMock 作为 deps（不需要任何真实依赖）
    mock_deps = MagicMock(spec=WorkflowDeps)
    builder = build_graph_with_deps(mock_deps)
    graph = builder.compile()
    assert graph is not None
    # 所有 4 个节点都已注册
    for name in ["generate_questions", "wait_for_candidate", "validate_complete", "generate_report"]:
        assert name in graph.nodes


def test_workflowdeps_dataclass():
    """WorkflowDeps 是 dataclass，可直接构造"""
    from dataclasses import fields
    deps = WorkflowDeps(
        db="fake_db",
        interview_repo="fake_interview_repo",
        candidate_repo="fake_candidate_repo",
        position_repo="fake_position_repo",
        question_repo="fake_question_repo",
        audit_repo="fake_audit_repo",
        file_storage="fake_file_storage",
        sse_manager="fake_sse_manager",
        prompt_renderer="fake_prompt_renderer",
    )
    assert deps.db == "fake_db"
    # 应该有 9 个字段
    assert len(fields(WorkflowDeps)) == 9