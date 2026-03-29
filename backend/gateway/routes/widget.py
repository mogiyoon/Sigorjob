from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.store import config_store
from db.models import Task, Schedule
from db.session import get_session
from tunnel import manager as tunnel

router = APIRouter()


@router.get("/widget/summary")
async def widget_summary(session: AsyncSession = Depends(get_session)):
    task_result = await session.execute(select(Task).order_by(Task.created_at.desc()).limit(5))
    schedule_result = await session.execute(select(Schedule).order_by(Schedule.created_at.desc()).limit(5))

    quick_actions = config_store.get(
        "widget_quick_actions",
        [
            {"label": "현재 위치", "command": "pwd"},
            {"label": "현재 시간", "command": "현재 시간"},
            {"label": "파일 목록", "command": "파일 목록 보여줘"},
        ],
    )

    return {
        "tunnel_active": bool(tunnel.get_url()),
        "recent_tasks": [
            {
                "task_id": row.id,
                "command": row.command,
                "status": row.status.value,
            }
            for row in task_result.scalars().all()
        ],
        "schedules": [
            {
                "schedule_id": row.id,
                "name": row.name,
                "status": row.status.value,
            }
            for row in schedule_result.scalars().all()
        ],
        "quick_actions": quick_actions,
    }
