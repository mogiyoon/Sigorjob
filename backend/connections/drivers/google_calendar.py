from __future__ import annotations

from urllib.parse import quote_plus

from connections.base import BaseConnectorDriver, Connection, ConnectionExecutionResult


class GoogleCalendarConnectorDriver(BaseConnectorDriver):
    driver_id = "google_calendar"
    connection_ids = ("google_calendar",)
    capabilities = ("create_calendar_event",)

    async def is_ready(self, connection: Connection) -> bool:
        return bool(connection.get("configured")) and bool(connection.get("verified"))

    async def execute(
        self,
        connection: Connection,
        capability: str,
        payload: dict,
    ) -> ConnectionExecutionResult:
        if capability != "create_calendar_event":
            return ConnectionExecutionResult(
                success=False,
                handled=False,
                error="unsupported capability",
            )

        if not await self.is_ready(connection):
            return ConnectionExecutionResult(
                success=False,
                handled=False,
                error="google calendar connection is not ready",
            )

        title = str(payload.get("title") or "").strip()
        details = str(payload.get("details") or "").strip()
        dates = str(payload.get("dates") or "").strip()
        if not title or not dates:
            return ConnectionExecutionResult(
                success=False,
                handled=False,
                error="calendar title and dates are required",
            )

        url = (
            "https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={quote_plus(title)}"
            f"&details={quote_plus(details)}"
            f"&dates={dates}"
        )
        return ConnectionExecutionResult(
            success=True,
            handled=True,
            data={
                "action": "open_url",
                "url": url,
                "title": f"캘린더에 {title} 추가",
                "calendar": {
                    "title": title,
                    "details": details,
                    "dates": dates,
                },
                "connector": {
                    "connection_id": connection.get("id"),
                    "driver_id": self.driver_id,
                    "capability": capability,
                    "execution_mode": "connected_link",
                },
            },
            metadata={
                "connection_id": connection.get("id"),
                "driver_id": self.driver_id,
                "capability": capability,
            },
        )
