import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db.models import Schedule, ScheduleStatus
from db.session import AsyncSessionLocal
from scheduler import service as scheduler_service
from tools.base import BaseTool

KST = ZoneInfo("Asia/Seoul")
KMA_URL = "https://www.weather.go.kr/w/index.do"


@dataclass
class WeatherAlertPlan:
    label: str
    hour: int
    minute: int
    cron: str
    source_name: str
    source_url: str
    command: str


class WeatherAlertHelperTool(BaseTool):
    name = "weather_alert_helper"
    description = "Create a recurring weather-check schedule from a natural-language request"

    async def run(self, params: dict) -> dict:
        raw_text = (params.get("text") or "").strip()
        if not raw_text:
            return {"success": False, "data": None, "error": "text is required"}

        plan = _build_plan(raw_text)
        existing = await _find_existing_schedule(plan.command, plan.cron)
        if existing is not None:
            return {
                "success": True,
                "data": {
                    "action": "schedule_created",
                    "schedule_id": existing.id,
                    "name": existing.name,
                    "cron": existing.cron,
                    "command": existing.command,
                    "source_name": plan.source_name,
                    "source_url": plan.source_url,
                    "delivery": "app_task_list",
                    "deduplicated": True,
                },
                "error": None,
            }

        schedule_id = str(uuid.uuid4())
        try:
            async with AsyncSessionLocal() as session:
                schedule = Schedule(
                    id=schedule_id,
                    name=plan.label,
                    command=plan.command,
                    cron=plan.cron,
                    status=ScheduleStatus.active,
                    next_run_at=scheduler_service.next_run_time(plan.cron),
                )
                session.add(schedule)
                await session.commit()

            await scheduler_service.create(schedule_id, plan.command, plan.cron)
            return {
                "success": True,
                "data": {
                    "action": "schedule_created",
                    "schedule_id": schedule_id,
                    "name": plan.label,
                    "cron": plan.cron,
                    "command": plan.command,
                    "source_name": plan.source_name,
                    "source_url": plan.source_url,
                    "delivery": "app_task_list",
                    "deduplicated": False,
                },
                "error": None,
            }
        except SQLAlchemyError:
            return {
                "success": True,
                "data": {
                    "action": "schedule_draft",
                    "schedule_id": None,
                    "name": plan.label,
                    "cron": plan.cron,
                    "command": plan.command,
                    "source_name": plan.source_name,
                    "source_url": plan.source_url,
                    "delivery": "app_task_list",
                    "deduplicated": False,
                },
                "error": None,
            }


def register_tools(register):
    register(WeatherAlertHelperTool())


async def _find_existing_schedule(command: str, cron: str) -> Schedule | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).where(
                Schedule.command == command,
                Schedule.cron == cron,
                Schedule.status == ScheduleStatus.active,
            )
        )
        return result.scalar_one_or_none()


def _build_plan(text: str) -> WeatherAlertPlan:
    hour, minute = _extract_time(text)
    cron = f"{minute} {hour} * * *"
    source_name = "기상청" if "기상청" in text else "날씨 페이지"
    source_url = KMA_URL
    command = f"{source_url} 읽어와 모바일로 날씨 알려줘"
    label = f"매일 {hour:02d}:{minute:02d} {source_name} 날씨 확인"
    return WeatherAlertPlan(
        label=label,
        hour=hour,
        minute=minute,
        cron=cron,
        source_name=source_name,
        source_url=source_url,
        command=command,
    )


def _extract_time(text: str) -> tuple[int, int]:
    match = re.search(r"(오전|오후|아침|저녁|밤)?\s*(\d{1,2})시(?:\s*(\d{1,2})분)?", text)
    if not match:
        return 8, 0

    period = match.group(1) or ""
    hour = int(match.group(2))
    minute = int(match.group(3) or 0)

    if period in {"오후", "저녁", "밤"} and hour < 12:
        hour += 12
    if period == "오전" and hour == 12:
        hour = 0
    if period == "아침" and hour == 12:
        hour = 8

    hour = max(0, min(hour, 23))
    minute = max(0, min(minute, 59))
    return hour, minute
