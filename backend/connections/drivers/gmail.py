from __future__ import annotations

import asyncio
import base64
from email.mime.text import MIMEText
from typing import Any

from connections import oauth
from connections.base import BaseConnectorDriver, Connection, ConnectionExecutionResult


class GmailConnectorDriver(BaseConnectorDriver):
    driver_id = "gmail"
    connection_ids = ("gmail",)
    capabilities = ("send_email", "read_email")

    async def is_ready(self, connection: Connection) -> bool:
        return bool(connection.get("configured")) and bool(connection.get("verified"))

    async def execute(
        self,
        connection: Connection,
        capability: str,
        payload: dict[str, Any],
    ) -> ConnectionExecutionResult:
        if capability not in self.capabilities:
            return ConnectionExecutionResult(success=False, handled=False, error="unsupported capability")

        if not await self.is_ready(connection):
            return ConnectionExecutionResult(success=False, handled=False, error="gmail connection is not ready")

        access_token = await oauth.get_access_token(str(connection.get("id") or self.driver_id))
        if not access_token:
            return ConnectionExecutionResult(success=False, handled=True, error="not authenticated")

        try:
            if capability == "send_email":
                message_id = await self._send_email(access_token, payload)
                return ConnectionExecutionResult(
                    success=True,
                    handled=True,
                    data={
                        "message_id": message_id,
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

            messages = await self._read_email(access_token, payload)
            return ConnectionExecutionResult(
                success=True,
                handled=True,
                data={
                    "messages": messages,
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
        except RuntimeError as exc:
            return ConnectionExecutionResult(success=False, handled=True, error=str(exc))

    async def _send_email(self, access_token: str, payload: dict[str, Any]) -> str:
        to_address = str(payload.get("to") or "").strip()
        subject = str(payload.get("subject") or "").strip()
        body = str(payload.get("body") or payload.get("message") or "").strip()
        if not to_address or not subject or not body:
            raise RuntimeError("to, subject, and body are required")

        message = MIMEText(body)
        message["to"] = to_address
        message["subject"] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        service = await self._build_service(access_token)
        response = await self._run_google_call(
            lambda: service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
        )
        message_id = str((response or {}).get("id") or "").strip()
        if not message_id:
            raise RuntimeError("gmail api response did not include message id")
        return message_id

    async def _read_email(self, access_token: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        max_results = int(payload.get("max_results") or 10)
        query = str(payload.get("query") or "").strip()
        service = await self._build_service(access_token)
        listed = await self._run_google_call(
            lambda: service.users().messages().list(userId="me", maxResults=max_results, q=query or None).execute()
        )
        items = []
        for message_ref in (listed or {}).get("messages", []):
            message_id = str((message_ref or {}).get("id") or "").strip()
            if not message_id:
                continue
            detail = await self._run_google_call(
                lambda message_id=message_id: service.users()
                .messages()
                .get(userId="me", id=message_id, format="metadata")
                .execute()
            )
            payload_data = (detail or {}).get("payload") or {}
            headers = {str(item.get("name") or "").lower(): item.get("value") for item in payload_data.get("headers", [])}
            items.append(
                {
                    "id": message_id,
                    "thread_id": detail.get("threadId"),
                    "subject": headers.get("subject"),
                    "from": headers.get("from"),
                    "snippet": detail.get("snippet"),
                }
            )
        return items

    async def _build_service(self, access_token: str) -> Any:
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError("google-api-python-client and google-auth are required for Gmail API access") from exc

        def _build() -> Any:
            credentials = Credentials(token=access_token)
            return build("gmail", "v1", credentials=credentials, cache_discovery=False)

        return await asyncio.get_running_loop().run_in_executor(None, _build)

    async def _run_google_call(self, func) -> Any:
        return await asyncio.get_running_loop().run_in_executor(None, func)
