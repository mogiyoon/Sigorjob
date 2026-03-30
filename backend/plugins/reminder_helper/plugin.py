import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db.models import Schedule, ScheduleStatus
from db.session import AsyncSessionLocal
from scheduler import service as scheduler_service
from tools.base import BaseTool


@dataclass
class ReminderPlan:
    label: str
    cron: str
    command: str
    hour: int
    minute: int


class ReminderHelperTool(BaseTool):
    name = "reminder_helper"
    description = "Create a recurring reminder or summary schedule from a natural-language request"

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
                    "delivery": "mobile_notification",
                    "deduplicated": True,
                    "notify_mobile": True,
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
                    "delivery": "mobile_notification",
                    "deduplicated": False,
                    "notify_mobile": True,
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
                    "delivery": "mobile_notification",
                    "deduplicated": False,
                    "notify_mobile": True,
                },
                "error": None,
            }


def register_tools(register):
    register(ReminderHelperTool())


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


def _build_plan(text: str) -> ReminderPlan:
    hour, minute = _extract_time(text)
    cron = f"{minute} {hour} * * *"
    action = _extract_action(text)
    command = _build_command(action)
    label = f"매일 {hour:02d}:{minute:02d} {action}"
    return ReminderPlan(label=label, cron=cron, command=command, hour=hour, minute=minute)


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


def _extract_action(text: str) -> str:
    cleaned = re.sub(r"(오전|오후|아침|저녁|밤)?\s*\d{1,2}시(?:\s*\d{1,2}분)?에?", "", text)
    cleaned = re.sub(
        r"\s*(알람으로 보내줘|알림으로 보내줘|알람 보내줘|알림 보내줘|알람 해줘|알림 해줘|리마인드해줘|리마인드 해줘)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*(해서|해서는|하고)\s*$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" \"'")
    return cleaned or "요약 알려주기"


def _build_command(action: str) -> str:
    if "모바일" in action or "알림" in action:
        return action
    if action.endswith("요약"):
        return f"{action}해서 모바일로 알려줘"
    return f"{action} 모바일로 알려줘"
