from __future__ import annotations

from urllib.parse import quote_plus

from connections.base import BaseConnectorDriver, Connection, ConnectionExecutionResult


def _render_template(template: str, payload: dict) -> str:
    rendered = template
    for key, value in payload.items():
        token = "{" + key + "}"
        rendered = rendered.replace(token, quote_plus(str(value)))
    return rendered


class TemplateConnectorDriver(BaseConnectorDriver):
    driver_id = "template_connector"
    capabilities = (
        "create_calendar_event",
        "send_email",
        "read_email",
        "list_calendar_events",
    )

    async def is_ready(self, connection: Connection) -> bool:
        return bool(connection.get("configured")) and bool(connection.get("verified"))

    async def execute(
        self,
        connection: Connection,
        capability: str,
        payload: dict,
    ) -> ConnectionExecutionResult:
        templates = (connection.get("metadata") or {}).get("templates") or {}
        template = templates.get(capability)
        if not isinstance(template, dict):
            return ConnectionExecutionResult(
                success=False,
                handled=False,
                error="template for capability is missing",
            )

        url_template = str(template.get("url_template") or "").strip()
        title_template = str(template.get("title_template") or "").strip()
        if not url_template:
            return ConnectionExecutionResult(
                success=False,
                handled=False,
                error="url_template is required",
            )

        url = _render_template(url_template, payload)
        title = _render_template(title_template, payload) if title_template else connection.get("title") or "링크 열기"
        return ConnectionExecutionResult(
            success=True,
            handled=True,
            data={
                "action": "open_url",
                "url": url,
                "title": title,
                "connector": {
                    "connection_id": connection.get("id"),
                    "driver_id": self.driver_id,
                    "capability": capability,
                    "execution_mode": "template_link",
                },
            },
            metadata={
                "connection_id": connection.get("id"),
                "driver_id": self.driver_id,
                "capability": capability,
            },
        )
