from __future__ import annotations

from typing import Any

from config.store import config_store
from connections import oauth
from connections.registry import get_connection, get_mcp_server
from orchestrator.task import Step


CapabilityCheck = dict[str, Any]

_TOOL_CAPABILITY_MAP: dict[str, tuple[str, str]] = {}


def check_capabilities(steps: list[Step]) -> list[CapabilityCheck]:
    missing: list[CapabilityCheck] = []
    seen: set[tuple[str, str, str]] = set()

    for step in steps:
        result = check_capability(step)
        if result.get("satisfied", True):
            continue
        key = (
            str(result.get("connection_id") or ""),
            str(result.get("capability_name") or ""),
            str(result.get("setup_action") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        missing.append(result)

    return missing


def check_capability(step: Step) -> CapabilityCheck:
    requirement = _resolve_requirement(step)
    if requirement is None:
        return {"satisfied": True}

    connection_id, capability_name = requirement
    connection = get_connection(connection_id)
    granted_permissions = set(config_store.get("granted_permissions", []))
    required_permissions = set((connection or {}).get("required_permissions") or [])
    capability_permissions = set(((connection or {}).get("capability_permissions") or {}).get(capability_name, []))
    missing_permissions = sorted((required_permissions | capability_permissions) - granted_permissions)
    if missing_permissions:
        return _build_missing_result(
            connection_id=connection_id,
            capability_name=capability_name,
            setup_action="permission",
            setup_message=_permission_message(connection_id, capability_name),
            fallback_available=True,
            fallback_description=_fallback_description(connection_id, capability_name),
            missing_permissions=missing_permissions,
        )

    if connection_id in {"google_calendar", "gmail"} and oauth.get_stored_tokens(connection_id):
        return {
            "satisfied": True,
            "connection_id": connection_id,
            "capability_name": capability_name,
        }

    server = get_mcp_server(connection_id)
    if server is not None and step.tool == "mcp":
        return {
            "satisfied": True,
            "connection_id": connection_id,
            "capability_name": capability_name,
        }

    if step.tool == "mcp" and connection_id in {"google_calendar", "gmail"}:
        return _build_missing_result(
            connection_id=connection_id,
            capability_name=capability_name,
            setup_action="oauth",
            setup_message=_oauth_message(connection_id, capability_name),
            fallback_available=True,
            fallback_description=_fallback_description(connection_id, capability_name),
        )

    if connection_id in {"google_calendar", "gmail"}:
        return _build_missing_result(
            connection_id=connection_id,
            capability_name=capability_name,
            setup_action="oauth",
            setup_message=_oauth_message(connection_id, capability_name),
            fallback_available=True,
            fallback_description=_fallback_description(connection_id, capability_name),
        )

    if step.tool == "mcp":
        return _build_missing_result(
            connection_id=connection_id,
            capability_name=capability_name,
            setup_action="mcp_install",
            setup_message=_mcp_message(connection_id, capability_name),
            fallback_available=False,
            fallback_description="",
        )

    return {"satisfied": True}


def _resolve_requirement(step: Step) -> tuple[str, str] | None:
    if step.tool == "crawler":
        return None

    mapped = _TOOL_CAPABILITY_MAP.get(step.tool)
    if mapped is not None:
        return mapped

    if step.tool != "mcp":
        return None

    server_name = str(step.params.get("server") or "").strip()
    tool_name = str(step.params.get("tool") or "").strip()

    if server_name == "gmail":
        if "read" in tool_name:
            return "gmail", "read_email"
        return "gmail", "send_email"

    if server_name == "google_calendar":
        if "list" in tool_name:
            return "google_calendar", "list_calendar_events"
        return "google_calendar", "create_calendar_event"

    if server_name:
        capability_name = tool_name or "use_mcp_server"
        return server_name, capability_name

    return None


def _build_missing_result(
    *,
    connection_id: str,
    capability_name: str,
    setup_action: str,
    setup_message: str,
    fallback_available: bool,
    fallback_description: str,
    missing_permissions: list[str] | None = None,
) -> CapabilityCheck:
    return {
        "satisfied": False,
        "connection_id": connection_id,
        "capability_name": capability_name,
        "setup_action": setup_action,
        "setup_message": setup_message,
        "fallback_available": fallback_available,
        "fallback_description": fallback_description,
        "missing_permissions": missing_permissions or [],
    }


def _oauth_message(connection_id: str, capability_name: str) -> str:
    title = _connection_title(connection_id)
    capability_label = _capability_label(capability_name)
    return f"{title} 연결이 필요합니다. {capability_label}을(를) 계속하려면 OAuth 연결을 완료하세요. {title} connection is required. Complete OAuth setup to continue with {capability_label}."


def _permission_message(connection_id: str, capability_name: str) -> str:
    title = _connection_title(connection_id)
    capability_label = _capability_label(capability_name)
    return f"{title} 권한이 필요합니다. {capability_label}을(를) 실행하려면 필요한 권한을 허용하세요. {title} permissions are required. Grant the required permissions to continue with {capability_label}."


def _mcp_message(connection_id: str, capability_name: str) -> str:
    capability_label = _capability_label(capability_name)
    return f"{connection_id} MCP 서버 설정이 필요합니다. {capability_label}을(를) 계속하려면 MCP 서버를 설치하세요. The {connection_id} MCP server is required. Install it to continue with {capability_label}."


def _fallback_description(connection_id: str, capability_name: str) -> str:
    if connection_id == "google_calendar":
        return "연결을 거부하면 캘린더 링크로 대신 안내할 수 있습니다. If you decline, the task can fall back to a calendar link."
    if connection_id == "gmail":
        return "연결을 거부하면 메일 링크나 초안으로 대신 안내할 수 있습니다. If you decline, the task can fall back to a mail link or draft."
    return f"연결을 거부하면 제한된 방식으로 {capability_name}을(를) 안내할 수 있습니다. If you decline, the task may fall back to a limited {capability_name} flow."


def _connection_title(connection_id: str) -> str:
    connection = get_connection(connection_id)
    return str((connection or {}).get("title") or connection_id)


def _capability_label(capability_name: str) -> str:
    return capability_name.replace("_", " ")
