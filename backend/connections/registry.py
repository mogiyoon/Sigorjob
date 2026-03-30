from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai.runtime import has_api_key
from config.secret_store import secret_store
from config.store import config_store
from tunnel import manager as tunnel


Connection = dict[str, Any]


DEFAULT_EXTERNAL_CONNECTIONS: list[Connection] = [
    {
        "id": "gmail",
        "title": "Gmail",
        "description": "Send and read email through a connected Gmail account or a Gmail-compatible MCP server.",
        "provider": "google",
        "kind": "external",
        "connection_type": "oauth_or_mcp",
        "required_permissions": ["external_connection_access", "email_send_access"],
        "configured": False,
        "verified": False,
        "available": False,
        "account_label": None,
        "metadata": {},
        "status": "not_connected",
        "next_action": "connect",
    },
    {
        "id": "google_calendar",
        "title": "Google Calendar",
        "description": "Create or manage calendar events through a connected Google account or a calendar MCP server.",
        "provider": "google",
        "kind": "external",
        "connection_type": "oauth_or_mcp",
        "required_permissions": ["external_connection_access", "calendar_event_creation"],
        "configured": False,
        "verified": False,
        "available": False,
        "account_label": None,
        "metadata": {},
        "status": "not_connected",
        "next_action": "connect",
    },
    {
        "id": "mcp_runtime",
        "title": "MCP runtime",
        "description": "Enable external MCP servers so Sigorjob can grow without adding one-off popups or feature-specific flows.",
        "provider": "mcp",
        "kind": "external",
        "connection_type": "runtime",
        "required_permissions": ["external_connection_access", "mcp_runtime_access"],
        "configured": False,
        "verified": False,
        "available": True,
        "account_label": None,
        "metadata": {},
        "status": "planned",
        "next_action": "setup",
    },
]


def list_connections() -> list[Connection]:
    items: list[Connection] = [
        _build_mobile_connection(),
        _build_ai_connection(),
    ]
    items.extend(_build_external_connections())
    return items


def get_connection(connection_id: str) -> Connection | None:
    for item in list_connections():
        if item["id"] == connection_id:
            return item
    return None


def update_external_connection(
    connection_id: str,
    *,
    configured: bool | None = None,
    verified: bool | None = None,
    account_label: str | None = None,
    available: bool | None = None,
    metadata: dict[str, Any] | None = None,
) -> Connection | None:
    stored = config_store.get("external_connections", {})
    current = dict(stored.get(connection_id, {}))

    if configured is not None:
        current["configured"] = configured
    if verified is not None:
        current["verified"] = verified
    if account_label is not None:
        current["account_label"] = account_label
    if available is not None:
        current["available"] = available
    if metadata is not None:
        current["metadata"] = metadata

    stored[connection_id] = current
    config_store.set("external_connections", stored)
    return get_connection(connection_id)


def _build_mobile_connection() -> Connection:
    url = tunnel.get_url()
    available = tunnel.is_installed()
    configured = config_store.get("tunnel_mode", "none") in {"quick", "cloudflare"}
    verified = bool(url)
    if verified:
        status = "connected"
        next_action = "manage"
    elif configured:
        status = "configured"
        next_action = "start"
    elif not available:
        status = "missing_dependency"
        next_action = "install"
    else:
        status = "not_connected"
        next_action = "connect"

    return {
        "id": "mobile_connection",
        "title": "Mobile connection",
        "description": "Lets your phone securely reach this device through the built-in mobile access flow.",
        "provider": "cloudflare",
        "kind": "core",
        "connection_type": "tunnel",
        "required_permissions": ["mobile_remote_access"],
        "configured": configured,
        "verified": verified,
        "available": available,
        "account_label": None,
        "metadata": {
            "tunnel_mode": config_store.get("tunnel_mode", "none"),
            "tunnel_url": url,
        },
        "status": status,
        "next_action": next_action,
    }


def _build_ai_connection() -> Connection:
    configured = has_api_key()
    verified = bool(config_store.get("ai_verified", False)) if configured else False
    available = configured or bool(secret_store.backend("anthropic_api_key"))
    if verified:
        status = "connected"
        next_action = "manage"
    elif configured:
        status = "configured"
        next_action = "verify"
    else:
        status = "not_connected"
        next_action = "connect"

    return {
        "id": "anthropic_ai",
        "title": "Anthropic AI",
        "description": "Used when non-AI automation needs help with planning, review, or continuation.",
        "provider": "anthropic",
        "kind": "core",
        "connection_type": "api_key",
        "required_permissions": ["ai_fallback_access"],
        "configured": configured,
        "verified": verified,
        "available": available,
        "account_label": None,
        "metadata": {
            "validation_error": config_store.get("ai_validation_error"),
            "storage_backend": secret_store.backend("anthropic_api_key"),
        },
        "status": status,
        "next_action": next_action,
    }


def _build_external_connections() -> list[Connection]:
    stored = config_store.get("external_connections", {})
    items: list[Connection] = []
    for default in DEFAULT_EXTERNAL_CONNECTIONS:
        item = deepcopy(default)
        saved = stored.get(item["id"], {})
        item["configured"] = bool(saved.get("configured", item["configured"]))
        item["verified"] = bool(saved.get("verified", item["verified"]))
        item["available"] = bool(saved.get("available", item["available"]))
        item["account_label"] = saved.get("account_label", item["account_label"])
        item["metadata"] = saved.get("metadata", item["metadata"])
        if item["verified"]:
            item["status"] = "connected"
            item["next_action"] = "manage"
        elif item["configured"]:
            item["status"] = "configured"
            item["next_action"] = "verify"
        elif item["available"]:
            item["status"] = "available"
            item["next_action"] = "connect"
        items.append(item)
    return items
