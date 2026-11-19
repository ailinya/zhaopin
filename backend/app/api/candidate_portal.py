"""
Candidate Portal API（§12，候选人端）

候选人不需要 JWT，只通过 URL token 鉴权：
- GET  /api/candidate/{token}/info                获取面试信息
- GET  /api/candidate/{token}/questions/next      获取下一题
- POST /api/candidate/{token}/answers              提交答案（multipart audio）
- PATCH /api/candidate/{token}/preferences         切换语音朗读
"""
from datetime import datetime
import asyncio

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.errors import APIError, ErrorCode
from app.deps import get_db, get_current_candidate
from app.models import (
    Interview, InterviewRepository,
    InterviewQuestion, InterviewQuestionRepository,
    Position, PositionRepository,
    Candidate, CandidateRepository,
    AuditLogRepository,
)
from app.schemas.portal import (
    CandidateInterviewInfo,
    QuestionOut,
    SubmitAnswerResponse,
    VoiceReadingToggle,
    VoiceReadingResponse,
)
from app.schemas.response import APIResponse


router = APIRouter(prefix="/api/candidate", tags=["candidate-portal"])


# ===== 端点 =====

@router.get("/{token}/info", response_model=APIResponse[CandidateInterviewInfo])
async def get_info(
    interview: Interview = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """获取候选人面试信息"""
    # 如果面试状态为0（待开始），自动改为1（进行中）
    if interview.status == 0:
        interview.status = 1
        db.commit()

    # 如果没有题目，自动触发工作流生成题目
    from app.models import InterviewQuestionRepository
    q_repo = InterviewQuestionRepository(db)
    existing_questions = q_repo.list_by_interview(interview.id)
    if len(existing_questions) == 0 and interview.question_count is None:
        # 题目尚未生成，触发工作流
        from app.services.workflow_service import run_for_interview
        run_for_interview(
            interview_id=interview.id,
            thread_id=interview.langgraph_thread_id,
        )

    candidate = CandidateRepository(db).get(interview.candidate_id)
    position = PositionRepository(db).get(interview.position_id)

    if not candidate or not position:
        raise APIError.not_found(
            ErrorCode.CANDIDATE_NOT_FOUND if not candidate else ErrorCode.POSITION_NOT_FOUND,
            "面试关联数据缺失",
        )

    # 格式化时间
    time_str = "未设置时间"
    if interview.start_time:
        time_str = datetime.fromtimestamp(interview.start_time).strftime("%Y年%m月%d日 %H:%M")

    return APIResponse.ok(
        CandidateInterviewInfo(
            interview_id=interview.id,
            candidate_name=candidate.name,
            position_name=position.name,
            time=time_str,
            status=interview.status,
            question_count=interview.question_count or 0,
            answered_count=interview.answered_count or 0,
            voice_reading=bool(interview.voice_reading),
        )
    )


@router.get("/{token}/questions/next", response_model=APIResponse[QuestionOut])
async def get_next_question(
    after: int = Query(default=0, description="当前题 ID，0 表示取第一题"),
    interview: Interview = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """获取下一题"""
    q_repo = InterviewQuestionRepository(db)
    next_q = q_repo.get_next(interview_id=interview.id, after_id=after)

    if not next_q:
        # 面试已完成
        return APIResponse.ok(QuestionOut(id=0, text="面试已完成"))

    return APIResponse.ok(QuestionOut(id=next_q.id, text=next_q.question))


@router.post("/{token}/answers", response_model=APIResponse[SubmitAnswerResponse])
async def submit_answer(
    token: str,
    question_id: int = Form(...),
    audio_answer: UploadFile = File(...),
    interview: Interview = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """提交答案（音频文件）

    Week 1：仅保存音频 + 标记已答
    Week 2：后台 Whisper 转写 + 触发 workflow resume（最后一题时）
    """
    q_repo = InterviewQuestionRepository(db)

    # 验证 question 属于这个 interview
    question = q_repo.get(question_id)
    if not question or question.interview_id != interview.id:
        raise APIError.not_found(
            ErrorCode.QUESTION_NOT_FOUND,
            f"题目 {question_id} 不存在或不属于本面试",
        )

    if question.answered_at is not None:
        raise APIError.conflict(
            ErrorCode.INVALID_STATE_TRANSITION,
            "该题已回答，不能重复提交",
        )

    # 保存音频 BLOB
    audio_data = await audio_answer.read()
    question.answer_audio = audio_data
    question.answered_at = int(datetime.utcnow().timestamp())

    # 增加面试进度
    InterviewRepository(db).increment_answered(interview.id)

    # 审计
    AuditLogRepository(db).create(
        event_type="answer_submitted",
        actor_id=interview.candidate_id,
        actor_type="candidate",
        interview_id=interview.id,
        metadata={"question_id": question_id, "audio_size": len(audio_data)},
    )

    db.commit()

    # 在后台线程触发 Whisper 转写（不阻塞 API 响应）
    # Week 7：把转写结果写回 question.answer_text
    import logging
    logger = logging.getLogger(__name__)

    async def _do_transcribe(
        _audio_data: bytes,
        _interview_id: int,
        _candidate_id: str,
        _question_id: int,
    ) -> None:
        """后台 ASR 转写 + 写回 answer_text

        任何一步失败必须写 audit_log（与 generate_report_node 一致），
        否则下次又只能看到 answer_text=NULL，无任何痕迹可查。
        """
        from functools import partial

        from app.core.main_loop import get_main_loop
        from app.database import SessionLocal
        from app.models import AuditLogRepository, InterviewQuestionRepository
        from app.services.asr_service import transcribe
        from app.services.file_storage import get_file_storage

        def _write_audit(event_type: str, meta: dict) -> None:
            """写一条 audit_log（独立 session，失败只 log 不再抛）"""
            s = SessionLocal()
            try:
                AuditLogRepository(s).create(
                    event_type=event_type,
                    actor_id=_candidate_id,
                    actor_type="system",
                    interview_id=_interview_id,
                    metadata=meta,
                )
                s.commit()
            except Exception:
                logger.exception("audit_log_write_failed", extra=meta)
            finally:
                s.close()

        try:
            # 1. 保存音频到文件
            storage = get_file_storage()
            audio_path = storage.save_audio(_interview_id, _question_id, _audio_data)

            # 2. 转写（阻塞调用，跑在默认 executor）
            main_loop = get_main_loop()
            text = await main_loop.run_in_executor(
                None, partial(transcribe, audio_path, "zh")
            )

            # 3. 写回 answer_text
            s = SessionLocal()
            try:
                InterviewQuestionRepository(s).update_answer(
                    _question_id, answer_text=text
                )
                s.commit()
            finally:
                s.close()

            # 4. 成功审计（便于以后排查"哪些题转了/没转"）
            _write_audit(
                "answer_transcribed",
                {
                    "question_id": _question_id,
                    "audio_path": str(audio_path),
                    "text_len": len(text),
                },
            )

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.exception(
                "transcribe_failed",
                extra={
                    "interview_id": _interview_id,
                    "question_id": _question_id,
                    "error": str(e),
                },
            )
            # 关键：失败也要留痕，与 generate_report_node_failed 同样的可观测性
            _write_audit(
                "answer_transcribe_failed",
                {
                    "question_id": _question_id,
                    "error": str(e),
                    "traceback": tb[-1500:],  # 截断避免太大
                },
            )

    def _task_done_callback(task: asyncio.Task) -> None:
        """task 兜底：正常路径下 _do_transcribe 已自处理异常，
        这里只在「未捕获异常」时再记录一次。"""
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.exception("transcribe_task_uncaught", exc_info=exc)

    # 调度后台任务
    try:
        running_loop = asyncio.get_running_loop()
        task = running_loop.create_task(
            _do_transcribe(audio_data, interview.id, interview.candidate_id, question_id)
        )
        task.add_done_callback(_task_done_callback)
    except RuntimeError:
        # 没有 event loop（罕见），用线程
        import threading

        def _run() -> None:
            try:
                asyncio.run(
                    _do_transcribe(audio_data, interview.id, interview.candidate_id, question_id)
                )
            except Exception:
                logger.exception("transcribe_thread_failed")

        threading.Thread(target=_run, daemon=True).start()

    # Week 2: 检查是否最后一题，若是则触发 workflow resume
    if q_repo.count_answered(interview.id) >= interview.question_count:
        # 触发 workflow 恢复（后台线程）
        from app.services.workflow_service import resume_after_completion
        resume_after_completion(
            thread_id=interview.langgraph_thread_id,
            answered_count=q_repo.count_answered(interview.id),
        )

    # 获取下一题
    next_q = q_repo.get_next(interview_id=interview.id, after_id=question_id)

    # increment_answered 内部已 commit + refresh，identity map 让 interview 对象同步
    answered_count = interview.answered_count or 0

    if next_q:
        return APIResponse.ok(
            SubmitAnswerResponse(
                answered_count=answered_count,
                next_question=QuestionOut(id=next_q.id, text=next_q.question),
            )
        )
    else:
        return APIResponse.ok(
            SubmitAnswerResponse(
                answered_count=answered_count,
                next_question=QuestionOut(id=0, text="面试已完成"),
            )
        )


@router.patch("/{token}/preferences", response_model=APIResponse[VoiceReadingResponse])
async def toggle_voice_reading(
    data: VoiceReadingToggle,
    interview: Interview = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """切换候选人语音朗读设置"""
    InterviewRepository(db).update_voice_reading(interview.id, data.enabled)

    AuditLogRepository(db).create(
        event_type="voice_reading_toggled",
        actor_id=interview.candidate_id,
        actor_type="candidate",
        interview_id=interview.id,
        metadata={"enabled": data.enabled},
    )

    return APIResponse.ok(VoiceReadingResponse(voice_reading=data.enabled))