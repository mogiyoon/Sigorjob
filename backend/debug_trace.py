import json
import uuid
from typing import Any

from db.models import TaskTraceEvent
from db.session import AsyncSessionLocal


SENSITIVE_DETAIL_KEYS = {
    "text",
    "body",
    "subject",
    "message",
    "content",
    "token",
    "_token",
    "authorization",
    "auth",
    "api_key",
    "anthropic_api_key",
    "cloudflare_tunnel_token",
    "recipient",
    "email",
    "url",
}


def _sanitize_detail(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if lowered in SENSITIVE_DETAIL_KEYS:
                sanitized[key] = "<redacted>"
            elif lowered == "params" and isinstance(item, dict):
                sanitized[key] = {
                    "keys": sorted(item.keys()),
                    "size": len(item),
                }
            else:
                sanitized[key] = _sanitize_detail(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_detail(item) for item in value[:20]]
    if isinstance(value, str):
        return f"<str:{len(value)}>"
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return f"<{type(value).__name__}>"


async def record_task_trace(
    task_id: str,
    *,
    stage: str,
    event: str,
    status: str | None = None,
    detail: dict[str, Any] | None = None,
    session=None,
) -> None:
    payload = json.dumps(_sanitize_detail(detail or {}), ensure_ascii=False)
    row = TaskTraceEvent(
        id=str(uuid.uuid4()),
        task_id=task_id,
        stage=stage,
        event=event,
        status=status,
        detail=payload,
    )

    if session is not None:
        session.add(row)
        await session.commit()
        return

    async with AsyncSessionLocal() as owned_session:
        owned_session.add(row)
        await owned_session.commit()
