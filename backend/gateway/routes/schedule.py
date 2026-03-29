import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.triggers.cron import CronTrigger

from db.models import Schedule, ScheduleStatus
from db.session import get_session
from scheduler import service as scheduler_service

router = APIRouter()


class ScheduleRequest(BaseModel):
    name: str
    command: str
    cron: str


@router.post("/schedule")
async def create_schedule(req: ScheduleRequest, session: AsyncSession = Depends(get_session)):
    CronTrigger.from_crontab(req.cron)
    schedule = Schedule(
        id=str(uuid.uuid4()),
        name=req.name.strip(),
        command=req.command.strip(),
        cron=req.cron.strip(),
        status=ScheduleStatus.active,
        created_at=datetime.now(timezone.utc),
        next_run_at=scheduler_service.next_run_time(req.cron.strip()),
    )
    session.add(schedule)
    await session.commit()
    await scheduler_service.create(schedule.id, schedule.command, schedule.cron)
    return {"schedule_id": schedule.id, "status": schedule.status.value}


@router.get("/schedules")
async def list_schedules(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Schedule).order_by(Schedule.created_at.desc()))
    rows = result.scalars().all()
    return {
        "schedules": [
            {
                "schedule_id": row.id,
                "name": row.name,
                "command": row.command,
                "cron": row.cron,
                "status": row.status.value,
                "created_at": row.created_at.isoformat(),
                "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
                "next_run_at": row.next_run_at.isoformat() if row.next_run_at else None,
            }
            for row in rows
        ]
    }


@router.delete("/schedule/{schedule_id}")
async def delete_schedule(schedule_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Schedule).where(Schedule.id == schedule_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="schedule not found")

    await scheduler_service.delete(schedule_id)
    await session.delete(row)
    await session.commit()
    return {"schedule_id": schedule_id, "status": "deleted"}
