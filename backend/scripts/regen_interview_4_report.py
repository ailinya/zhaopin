"""
一次性脚本：重跑 interview 4 的报告（用补转写后的 answer_text）

用法：
  cd G:/python_work/smart_interview_ai/backend
  python scripts/regen_interview_4_report.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# 确保 ffmpeg 在 PATH（虽然 regenerate 不需要，但保险起见）
from app.core.ffmpeg import ensure_ffmpeg_in_path
ensure_ffmpeg_in_path()

from app.database import SessionLocal
from app.workflow.nodes import generate_report_node
from app.workflow.dependencies import build_deps_from_db
from app.models import Interview
from app.schemas.llm import ReportEvaluation


def main() -> int:
    interview_id = 4
    s = SessionLocal()
    try:
        interview = s.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            print(f"[ERR] interview {interview_id} not found", file=sys.stderr)
            return 1

        print(f"[INFO] regenerating report for interview {interview_id}")
        print(f"[INFO] candidate_id={interview.candidate_id}, status={interview.status}")
        print(f"[INFO] report_path={interview.report_path}")

        deps = build_deps_from_db(s)
        try:
            state = {
                "interview_id": interview_id,
                "langgraph_thread_id": interview.langgraph_thread_id,
                "candidate_id": interview.candidate_id,
                "position_id": interview.position_id,
                "error": None,
                "error_node": None,
            }

            result = generate_report_node(state, deps=deps)
            print(f"[INFO] generate_report_node result keys: {list(result.keys())}")

            if result.get("error"):
                print(f"[ERR] {result['error']}")
                return 2

            # 重新读 interview 看 report_path 是否更新
            s.refresh(interview)
            print(f"[OK] new report_path: {interview.report_path}")
            print(f"[OK] new is_passed: {interview.is_passed}")
            return 0
        finally:
            deps.close()
    finally:
        s.close()


if __name__ == "__main__":
    sys.exit(main())