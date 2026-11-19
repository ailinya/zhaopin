"""
一次性脚本：补转写 interview 4 的 10 段音频到 DB

用法：
  cd G:/python_work/smart_interview_ai/backend
  python scripts/backfill_interview_4_transcripts.py
"""
import os
import sys
import traceback
from pathlib import Path

# 让脚本可以找到 app 包
sys.path.insert(0, str(Path(__file__).parent.parent))

# 确保 ffmpeg 在 PATH
from app.core.ffmpeg import ensure_ffmpeg_in_path
ensure_ffmpeg_in_path()

import whisper
from app.database import SessionLocal
from app.models import InterviewQuestion, AuditLogRepository, InterviewQuestionRepository


def main() -> int:
    interview_id = 4
    audio_dir = Path(f"storage/audio/{interview_id}")
    if not audio_dir.is_dir():
        print(f"[ERR] audio dir not found: {audio_dir}", file=sys.stderr)
        return 1

    # 找出所有 webm，按 question_id 排序
    webm_files = sorted(audio_dir.glob("*.webm"), key=lambda p: int(p.stem))
    if not webm_files:
        print(f"[ERR] no .webm files in {audio_dir}", file=sys.stderr)
        return 1

    print(f"[INFO] found {len(webm_files)} audio files for interview {interview_id}")

    # 用项目的 transcribe() 函数，自动用 settings.WHISPER_MODEL + initial_prompt
    # 不再直接调 whisper.load_model + transcribe
    from app.config import settings
    print(f"[INFO] using whisper model={settings.WHISPER_MODEL}")

    # 加载模型一次（避免每个文件重新加载）
    from app.services.asr_service import (
        DEFAULT_INITIAL_PROMPT_ZH,
        load_whisper_model,
    )
    print("[INFO] loading whisper model...")
    load_whisper_model()
    from app.services.asr_service import get_model
    model = get_model()
    if model is None:
        print("[ERR] whisper model failed to load", file=sys.stderr)
        return 1
    print("[INFO] whisper model loaded")

    s = SessionLocal()
    q_repo = InterviewQuestionRepository(s)
    audit = AuditLogRepository(s)

    success_count = 0
    fail_count = 0

    try:
        for webm in webm_files:
            question_id = int(webm.stem)
            # 先看一下当前 question 状态
            q = s.query(InterviewQuestion).filter(InterviewQuestion.id == question_id).first()
            if not q:
                print(f"[WARN] question {question_id} not found in DB, skip")
                continue

            if q.answer_text and q.answer_text.strip() and not os.environ.get("FORCE_RETRANSCRIBE"):
                print(f"[SKIP] question {question_id} already has answer_text (len={len(q.answer_text)})")
                continue

            print(f"[INFO] transcribing question {question_id} from {webm.name} ({webm.stat().st_size//1024} KB)...")
            try:
                # faster-whisper API：segments 是 generator，text 在每个 seg.text
                segments, info = model.transcribe(
                    str(webm),
                    language="zh",
                    beam_size=5,
                    vad_filter=True,
                    initial_prompt=DEFAULT_INITIAL_PROMPT_ZH,
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()
                # 应用后处理（与 transcribe() 一致）
                from app.services.asr_service import _apply_term_fixes, _traditional_to_simplified
                text = _apply_term_fixes(text)
                text = _traditional_to_simplified(text)
                if not text:
                    print(f"[WARN] question {question_id} whisper returned empty text")
                    fail_count += 1
                    continue

                q_repo.update_answer(question_id, answer_text=text)
                s.commit()

                # 审计
                audit.create(
                    event_type="answer_transcribed_backfill",
                    actor_id="system",
                    actor_type="system",
                    interview_id=interview_id,
                    metadata={"question_id": question_id, "audio_path": str(webm), "text_len": len(text)},
                )
                s.commit()

                print(f"[OK] question {question_id}: {text[:80]}")
                success_count += 1
            except Exception as e:
                print(f"[ERR] question {question_id} failed: {e}")
                traceback.print_exc()
                fail_count += 1

        print(f"\n[SUMMARY] success={success_count} failed={fail_count}")
        return 0 if fail_count == 0 else 2
    finally:
        s.close()


if __name__ == "__main__":
    sys.exit(main())