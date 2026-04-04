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
        "auth_type": "oauth_or_mcp",
        "driver_id": "gmail",
        "capabilities": ["send_email", "read_email"],
        "capability_permissions": {
            "send_email": ["email_send_access"],
        },
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
        "auth_type": "oauth_or_mcp",
        "driver_id": "google_calendar",
        "capabilities": ["create_calendar_event", "list_calendar_events"],
        "capability_permissions": {
            "create_calendar_event": ["calendar_event_creation"],
        },
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
        "auth_type": "runtime",
        "driver_id": "mcp_runtime",
        "capabilities": [],
        "capability_permissions": {},
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

DEFAULT_CUSTOM_CONNECTOR: Connection = {
    "provider": "custom",
    "kind": "external",
    "connection_type": "custom",
    "auth_type": "manual",
    "driver_id": "template_connector",
    "capabilities": [],
    "capability_permissions": {},
    "required_permissions": ["external_connection_access"],
    "configured": False,
    "verified": False,
    "available": True,
    "account_label": None,
    "metadata": {},
    "status": "available",
    "next_action": "connect",
}


def list_connections() -> list[Connection]:
    items: list[Connection] = [
        _build_mobile_connection(),
        _build_ai_connection(),
    ]
    items.extend(_build_external_connections())
    items.extend(_build_custom_connections())
    return items


def get_connection(connection_id: str) -> Connection | None:
    for item in list_connections():
        if item["id"] == connection_id:
            return item
    return None


def list_mcp_servers() -> list[dict[str, Any]]:
    stored = config_store.get("mcp_servers", {})
    items: list[dict[str, Any]] = []

    if isinstance(stored, dict):
        for server_name, config in stored.items():
            if not isinstance(config, dict):
                continue
            item = dict(config)
            item["name"] = str(item.get("name") or server_name).strip()
            if item["name"]:
                items.append(item)
        return items

    if isinstance(stored, list):
        for config in stored:
            if not isinstance(config, dict):
                continue
            name = str(config.get("name") or config.get("id") or "").strip()
            if not name:
                continue
            item = dict(config)
            item["name"] = name
            items.append(item)

    return items


def get_mcp_server(server_name: str) -> dict[str, Any] | None:
    target = server_name.strip()
    if not target:
        return None

    for item in list_mcp_servers():
        if item.get("name") == target:
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


def upsert_custom_connection(
    connection_id: str,
    *,
    title: str | None = None,
    description: str | None = None,
    provider: str | None = None,
    auth_type: str | None = None,
    driver_id: str | None = None,
    capabilities: list[str] | None = None,
    capability_permissions: dict[str, list[str]] | None = None,
    configured: bool | None = None,
    verified: bool | None = None,
    account_label: str | None = None,
    available: bool | None = None,
    metadata: dict[str, Any] | None = None,
) -> Connection | None:
    cleaned_id = connection_id.strip()
    if not cleaned_id:
        return None

    stored = config_store.get("custom_connectors", {})
    current = dict(stored.get(cleaned_id, {}))
    if title is not None:
        current["title"] = title
    if description is not None:
        current["description"] = description
    if provider is not None:
        current["provider"] = provider
    if auth_type is not None:
        current["auth_type"] = auth_type
    if driver_id is not None:
        current["driver_id"] = driver_id
    if capabilities is not None:
        current["capabilities"] = capabilities
    if capability_permissions is not None:
        current["capability_permissions"] = capability_permissions
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

    stored[cleaned_id] = current
    config_store.set("custom_connectors", stored)
    return get_connection(cleaned_id)


def delete_custom_connection(connection_id: str) -> bool:
    cleaned_id = connection_id.strip()
    if not cleaned_id:
        return False
    stored = config_store.get("custom_connectors", {})
    if cleaned_id not in stored:
        return False
    stored.pop(cleaned_id, None)
    config_store.set("custom_connectors", stored)
    return True


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


def _build_custom_connections() -> list[Connection]:
    stored = config_store.get("custom_connectors", {})
    items: list[Connection] = []
    for connection_id, saved in stored.items():
        if not isinstance(saved, dict):
            continue
        item = deepcopy(DEFAULT_CUSTOM_CONNECTOR)
        item["id"] = connection_id
        item["title"] = saved.get("title") or connection_id
        item["description"] = saved.get("description") or "User-defined external connector."
        item["provider"] = saved.get("provider") or item["provider"]
        item["auth_type"] = saved.get("auth_type") or item["auth_type"]
        item["driver_id"] = saved.get("driver_id") or item["driver_id"]
        item["capabilities"] = list(saved.get("capabilities") or item["capabilities"])
        item["capability_permissions"] = dict(saved.get("capability_permissions") or item["capability_permissions"])
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
