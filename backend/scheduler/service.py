from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from db.models import Schedule, ScheduleStatus
from db.session import AsyncSessionLocal
from intent import router as intent_router
from orchestrator import engine as orchestrator
from logger.logger import get_logger

logger = get_logger(__name__)
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=str(timezone.utc))
    return _scheduler


async def start() -> None:
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
    await load_from_db()


async def stop() -> None:
    global _scheduler
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
    _scheduler = None


async def load_from_db() -> None:
    scheduler = get_scheduler()
    scheduler.remove_all_jobs()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Schedule).where(Schedule.status == ScheduleStatus.active))
        rows = result.scalars().all()

    for row in rows:
        _schedule_job(row.id, row.command, row.cron)


async def create(schedule_id: str, command: str, cron: str) -> None:
    _schedule_job(schedule_id, command, cron)


async def delete(schedule_id: str) -> None:
    scheduler = get_scheduler()
    scheduler.remove_job(schedule_id)


def _schedule_job(schedule_id: str, command: str, cron: str) -> None:
    scheduler = get_scheduler()
    trigger = CronTrigger.from_crontab(cron, timezone=str(timezone.utc))
    scheduler.add_job(
        _run_scheduled_task,
        trigger=trigger,
        args=[schedule_id, command],
        id=schedule_id,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


def next_run_time(cron: str) -> datetime | None:
    trigger = CronTrigger.from_crontab(cron, timezone=str(timezone.utc))
    return trigger.get_next_fire_time(None, datetime.now(timezone.utc))


async def _run_scheduled_task(schedule_id: str, command: str) -> None:
    logger.info(f"[schedule:{schedule_id}] running command: {command}")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Schedule).where(Schedule.id == schedule_id))
        row = result.scalar_one_or_none()
        if row is None or row.status != ScheduleStatus.active:
            return
        row.last_run_at = datetime.now(timezone.utc)
        row.next_run_at = next_run_time(row.cron)
        await session.commit()

    task = await intent_router.route(command)
    if not task.steps:
        logger.warning(f"[schedule:{schedule_id}] no executable steps generated")
        return

    try:
        await orchestrator.save_pending(task)
        await orchestrator.run(task)
    except Exception as exc:
        logger.error(f"[schedule:{schedule_id}] execution failed: {exc}")
