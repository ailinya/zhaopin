"""
APScheduler 后台调度（§10.7 + §13.4）

任务：
- check_stuck_interviews：每 5 分钟检查 status ∈ {1, 2, 3} 且 30 分钟未更新的面试
                  → 从 checkpoint 恢复 workflow
- (Phase 2) 清理过期 SSE 订阅
- (Phase 2) 定期清理 storage

集成到 lifespan（lifespan 启动时 start_scheduler，关闭时 stop_scheduler）。
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


logger = logging.getLogger(__name__)


# ===== Scheduler 单例 =====
_scheduler: AsyncIOScheduler | None = None


def _check_stuck_interviews() -> None:
    """
    巡检卡住的面试（§10.7）

    卡住定义：status ∈ {1, 2, 3}（试题已备好/进行中/完毕）且 30 分钟未更新
    处理：从 checkpoint 恢复 workflow（让 LangGraph 重新走完剩余节点）
    """
    from app.workflow.graph import resume_workflow, get_workflow_state
    from app.models import InterviewRepository
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        repo = InterviewRepository(session)
        stuck = repo.list_by_status(statuses=[1, 2, 3], older_than_minutes=30)
        if not stuck:
            return

        logger.info(f"stuck_interviews_found count={len(stuck)}")
        for interview in stuck:
            thread_id = interview.langgraph_thread_id
            try:
                state_snapshot = get_workflow_state(thread_id)
                if state_snapshot is None:
                    logger.warning(
                        "stuck_interview_no_checkpoint",
                        interview_id=interview.id,
                    )
                    continue
                # next 不为空说明 workflow 还在中间状态
                if state_snapshot.next:
                    logger.info(
                        "stuck_interview_resuming",
                        interview_id=interview.id,
                        next_node=str(state_snapshot.next),
                    )
                    # 不传 resume payload，让 graph 重新检查
                    resume_workflow(thread_id, None)
            except Exception as e:
                logger.error(
                    "stuck_interview_resume_failed",
                    interview_id=interview.id,
                    exc=str(e),
                )
    finally:
        session.close()


def start_scheduler() -> None:
    """启动 APScheduler（在 lifespan startup 调用）"""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler()

    # 卡住巡检：每 5 分钟
    _scheduler.add_job(
        _check_stuck_interviews,
        CronTrigger(minute="*/5"),
        id="check_stuck_interviews",
        name="Check stuck interviews and resume workflow",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("apscheduler_started jobs=check_stuck_interviews")


def stop_scheduler() -> None:
    """停止 APScheduler（在 lifespan shutdown 调用）"""
    global _scheduler
    if _scheduler is None:
        return

    try:
        _scheduler.shutdown(wait=False)
    except Exception as e:
        logger.warning(f"apscheduler_shutdown_error exc={e}")
    finally:
        _scheduler = None
    logger.info("apscheduler_stopped")