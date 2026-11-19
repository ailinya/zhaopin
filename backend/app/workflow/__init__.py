"""
LangGraph 工作流（§10）

4 节点线性流：
  START → generate_questions → wait_for_candidate (interrupt)
                                → validate_complete → generate_report → END
"""
from app.workflow.state import InterviewState

__all__ = ["InterviewState"]