from datetime import datetime, timedelta
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo
import re

from tools.base import BaseTool


KST = ZoneInfo("Asia/Seoul")


class CalendarHelperTool(BaseTool):
    name = "calendar_helper"
    description = "Prepare a Google Calendar event link from a natural-language schedule request"

    async def run(self, params: dict) -> dict:
        raw_text = (params.get("text") or "").strip()
        if not raw_text:
            return {"success": False, "data": None, "error": "text is required"}

        parsed = _parse_calendar_request(raw_text)
        url = (
            "https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={quote_plus(parsed['title'])}"
            f"&details={quote_plus(parsed['details'])}"
            f"&dates={parsed['dates']}"
        )
        return {
            "success": True,
            "data": {
                "action": "open_url",
                "url": url,
                "title": f"캘린더에 {parsed['title']} 추가",
                "calendar": parsed,
            },
            "error": None,
        }


def register_tools(register):
    register(CalendarHelperTool())


def _parse_calendar_request(text: str) -> dict:
    cleaned = text
    cleaned = re.sub(r"^캘린더에\s*", "", cleaned)
    cleaned = re.sub(r"\s*일정\s*추가해줘\s*$", "", cleaned)
    cleaned = re.sub(r"\s*일정\s*넣어줘\s*$", "", cleaned)
    cleaned = re.sub(r"\s*캘린더에\s*추가해줘\s*$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    start, end = _extract_time_range(cleaned)
    title = _extract_title(cleaned)
    details = f"Sigorjob에서 생성한 일정 초안: {cleaned}"
    return {
      "title": title,
      "details": details,
      "dates": f"{_format_google_datetime(start)}/{_format_google_datetime(end)}",
    }


def _extract_time_range(text: str) -> tuple[datetime, datetime]:
    now = datetime.now(KST)
    base_date = now.date()
    if "내일" in text:
        base_date = (now + timedelta(days=1)).date()
    elif "모레" in text:
        base_date = (now + timedelta(days=2)).date()

    hour = 9
    minute = 0
    match = re.search(r"(오전|오후)?\s*(\d{1,2})시(?:\s*(\d{1,2})분)?", text)
    if match:
        meridiem = match.group(1)
        hour = int(match.group(2))
        minute = int(match.group(3) or 0)
        if meridiem == "오후" and hour < 12:
            hour += 12
        if meridiem == "오전" and hour == 12:
            hour = 0

    start = datetime(
        year=base_date.year,
        month=base_date.month,
        day=base_date.day,
        hour=hour,
        minute=minute,
        tzinfo=KST,
    )
    end = start + timedelta(hours=1)
    return start, end


def _extract_title(text: str) -> str:
    title = re.sub(r"(오늘|내일|모레)", "", text)
    title = re.sub(r"(오전|오후)?\s*\d{1,2}시(?:\s*\d{1,2}분)?", "", title)
    title = re.sub(r"\s+", " ", title).strip(" -")
    return title or "새 일정"


def _format_google_datetime(value: datetime) -> str:
    return value.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
