from datetime import datetime, timedelta
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo
import re

from connections import manager as connection_manager
from connections import oauth
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
        fallback_data = self._build_fallback_link(parsed)
        if params.get("use_fallback"):
            return {
                "success": True,
                "data": fallback_data,
                "error": None,
            }

        if not oauth.get_stored_tokens("google_calendar"):
            return {
                "success": False,
                "data": {
                    "fallback_url": fallback_data["url"],
                    "fallback": fallback_data,
                },
                "error": "google calendar connection required",
            }

        connector_result = await connection_manager.execute_capability(
            "create_calendar_event",
            {
                "title": parsed["title"],
                "details": parsed["details"],
                "dates": parsed["dates"],
                "source_text": raw_text,
            },
        )
        if connector_result.handled and connector_result.success:
            return {
                "success": True,
                "data": connector_result.data,
                "error": None,
            }

        return {
            "success": False,
            "data": {
                "fallback_url": fallback_data["url"],
                "fallback": fallback_data,
            },
            "error": connector_result.error or "google calendar event creation failed",
        }

    def _build_fallback_link(self, parsed: dict) -> dict:
        url = (
            "https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={quote_plus(parsed['title'])}"
            f"&details={quote_plus(parsed['details'])}"
            f"&dates={parsed['dates']}"
        )
        return {
            "action": "open_url",
            "url": url,
            "title": f"캘린더에 {parsed['title']} 추가",
            "calendar": parsed,
            "connector": {
                "connection_id": None,
                "driver_id": None,
                "capability": "create_calendar_event",
                "execution_mode": "fallback_link",
            },
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
      "summary": _build_calendar_summary(start, title),
    }


def _extract_time_range(text: str) -> tuple[datetime, datetime]:
    now = datetime.now(KST)
    base_date = now.date()
    explicit_date = re.search(r"(?:(\d{4})년\s*)?(\d{1,2})월\s*(\d{1,2})일", text)
    if explicit_date:
        year = int(explicit_date.group(1) or now.year)
        month = int(explicit_date.group(2))
        day = int(explicit_date.group(3))
        base_date = datetime(year=year, month=month, day=day, tzinfo=KST).date()
    elif "내일" in text:
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
    title = re.sub(r"(?:(\d{4})년\s*)?\d{1,2}월\s*\d{1,2}일", "", title)
    title = re.sub(r"(오전|오후)?\s*\d{1,2}시(?:\s*\d{1,2}분)?(?:에)?", "", title)
    title = re.sub(r"\s*일정\s*(추가|넣기?)\s*$", "", title)
    title = re.sub(r"^\s*에\s*", "", title)
    title = re.sub(r"\s+", " ", title).strip(" -")
    return title or "새 일정"


def _build_calendar_summary(start: datetime, title: str) -> str:
    time_text = f"{start.month}월 {start.day}일 {start.hour}시에 **{title}** 일정을"
    if start.minute:
        time_text = f"{start.month}월 {start.day}일 {start.hour}시 {start.minute}분에 **{title}** 일정을"
    return time_text


def _format_google_datetime(value: datetime) -> str:
    return value.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
