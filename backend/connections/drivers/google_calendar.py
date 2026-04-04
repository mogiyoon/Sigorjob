from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote_plus

from connections import oauth
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

        access_token = await oauth.get_access_token(str(connection.get("id") or self.driver_id))
        if not access_token:
            return self._build_fallback_result(connection, capability, title, details, dates)

        try:
            event = await self._create_calendar_event(access_token, title, details, dates)
        except RuntimeError as exc:
            return ConnectionExecutionResult(
                success=False,
                handled=True,
                error=str(exc),
                metadata={
                    "connection_id": connection.get("id"),
                    "driver_id": self.driver_id,
                    "capability": capability,
                },
            )

        event_id = str(event.get("id") or "").strip()
        event_link = str(event.get("htmlLink") or "").strip()
        if not event_id or not event_link:
            return ConnectionExecutionResult(
                success=False,
                handled=True,
                error="google calendar api response was missing event details",
                metadata={
                    "connection_id": connection.get("id"),
                    "driver_id": self.driver_id,
                    "capability": capability,
                },
            )

        return ConnectionExecutionResult(
            success=True,
            handled=True,
            data={
                "action": "open_url",
                "url": event_link,
                "title": f"캘린더에 {title} 추가",
                "event_id": event_id,
                "event_link": event_link,
                "calendar": {
                    "title": title,
                    "details": details,
                    "dates": dates,
                    "event_id": event_id,
                    "event_link": event_link,
                },
                "connector": {
                    "connection_id": connection.get("id"),
                    "driver_id": self.driver_id,
                    "capability": capability,
                    "execution_mode": "google_api",
                },
            },
            metadata={
                "connection_id": connection.get("id"),
                "driver_id": self.driver_id,
                "capability": capability,
            },
        )

    def _build_fallback_result(
        self,
        connection: Connection,
        capability: str,
        title: str,
        details: str,
        dates: str,
    ) -> ConnectionExecutionResult:
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

    async def _create_calendar_event(
        self,
        access_token: str,
        title: str,
        details: str,
        dates: str,
    ) -> dict[str, Any]:
        start_at, end_at = self._parse_google_dates(dates)
        service = await self._build_service(access_token)
        event_body = {
            "summary": title,
            "description": details,
            "start": {"dateTime": start_at},
            "end": {"dateTime": end_at},
        }
        created = await self._run_google_call(
            lambda: service.events().insert(calendarId="primary", body=event_body).execute()
        )
        if not isinstance(created, dict):
            raise RuntimeError("google calendar api returned an invalid response")
        return created

    def _parse_google_dates(self, dates: str) -> tuple[str, str]:
        if "/" not in dates:
            raise RuntimeError("google calendar dates must be a start/end range")
        start_at, end_at = dates.split("/", 1)
        if not start_at or not end_at:
            raise RuntimeError("google calendar dates must include start and end")
        return self._google_to_rfc3339(start_at), self._google_to_rfc3339(end_at)

    def _google_to_rfc3339(self, value: str) -> str:
        if len(value) != 16 or not value.endswith("Z"):
            raise RuntimeError("google calendar datetime must be in UTC compact format")
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}T{value[9:11]}:{value[11:13]}:{value[13:15]}Z"

    async def _build_service(self, access_token: str) -> Any:
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "google-api-python-client and google-auth are required for Google Calendar API access"
            ) from exc

        def _build() -> Any:
            credentials = Credentials(token=access_token)
            return build("calendar", "v3", credentials=credentials, cache_discovery=False)

        return await asyncio.get_running_loop().run_in_executor(None, _build)

    async def _run_google_call(self, func) -> Any:
        return await asyncio.get_running_loop().run_in_executor(None, func)
