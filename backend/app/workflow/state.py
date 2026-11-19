"""
Interview LangGraph 状态（§10.3）

InterviewState TypedDict 定义工作流运行时数据。
"""
from typing import TypedDict, Optional


class InterviewQuestionDict(TypedDict, total=False):
    """题目 dict（与 DB interview_questions 表对应）"""
    id: int
    interview_id: int
    question: str
    score_standard: str
    difficulty: str  # hard / medium / easy


class InterviewAnswerDict(TypedDict, total=False):
    """答案 dict（与 DB interview_questions.answer_text 对应）"""
    question_id: int
    answer_text: str
    answered_at: int


class InterviewState(TypedDict, total=False):
    """面试工作流状态"""

    # ===== 标识 =====
    interview_id: int
    langgraph_thread_id: str
    candidate_id: str
    position_id: int

    # ===== 输入（节点 A 读取）=====
    resume_text: str                     # 从 DB 读
    position_name: str
    position_requirements: str
    position_responsibilities: str

    # ===== 出题结果（节点 A 输出）=====
    questions: list[dict]                # InterviewQuestionDict[]
    question_count: int
    difficulty_distribution: dict       # {"hard": N, "medium": N, "easy": N}

    # ===== 答题进度（节点 C 输出）=====
    answered_count: int
    pending_question_ids: list[int]     # 还没答的题

    # ===== 报告结果（节点 D 输出）=====
    report_id: Optional[int]
    report_path: Optional[str]

    # ===== 错误处理 =====
    error: Optional[str]
    error_node: Optional[str]            # 哪个节点失败