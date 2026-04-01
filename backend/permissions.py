from typing import Any

from config.store import config_store
from plugins import describe_plugins


CORE_PERMISSIONS: list[dict[str, Any]] = [
    {
        "id": "mobile_remote_access",
        "title": "모바일 원격 연결",
        "description": "모바일 앱과 외부 접속을 위해 터널 연결을 사용합니다.",
        "source": "core",
        "required_for": ["remote_access", "mobile_pairing"],
        "group": "core_access",
        "group_title": "핵심 접근",
        "priority": 10,
        "advanced": False,
    },
    {
        "id": "ai_fallback_access",
        "title": "AI fallback",
        "description": "비AI 처리로 부족한 경우 AI가 계획과 요약을 돕습니다.",
        "source": "core",
        "required_for": ["ai_planning", "ai_review"],
        "group": "core_access",
        "group_title": "핵심 접근",
        "priority": 20,
        "advanced": False,
    },
    {
        "id": "external_connection_access",
        "title": "외부 서비스 연결",
        "description": "Gmail, Google Calendar, MCP 같은 외부 기능을 연결할 수 있습니다.",
        "source": "core",
        "required_for": ["external_connections", "oauth_setup", "mcp_runtime"],
        "group": "service_extensions",
        "group_title": "서비스 확장",
        "priority": 30,
        "advanced": False,
    },
    {
        "id": "email_send_access",
        "title": "이메일 전송",
        "description": "연결된 메일 서비스로 실제 메일 전송을 허용합니다.",
        "source": "core",
        "required_for": ["send_email", "gmail_send"],
        "risk": "high",
        "group": "sensitive_actions",
        "group_title": "민감 작업",
        "priority": 100,
        "advanced": False,
    },
    {
        "id": "mcp_runtime_access",
        "title": "MCP 실행",
        "description": "외부 MCP 서버를 붙여 Sigorjob 기능을 확장합니다.",
        "source": "core",
        "required_for": ["mcp_runtime", "external_tools"],
        "group": "service_extensions",
        "group_title": "서비스 확장",
        "priority": 40,
        "advanced": True,
    },
]


def list_permissions(*, ai_configured: bool, tunnel_configured: bool) -> list[dict[str, Any]]:
    granted_permissions = set(config_store.get("granted_permissions", []))
    items: list[dict[str, Any]] = []

    for perm in CORE_PERMISSIONS:
        permission = dict(perm)
        if permission["id"] == "mobile_remote_access":
            permission["granted"] = permission["id"] in granted_permissions or tunnel_configured
        elif permission["id"] == "ai_fallback_access":
            permission["granted"] = permission["id"] in granted_permissions or ai_configured
        else:
            permission["granted"] = permission["id"] in granted_permissions
        permission["risk"] = permission.get("risk", "low")
        items.append(permission)

    for plugin in describe_plugins():
        for permission in plugin.get("permissions", []):
            item = dict(permission)
            item["source"] = plugin["name"]
            item["granted"] = item["id"] in granted_permissions
            item["risk"] = item.get("risk", "low")
            item["group"] = item.get("group", "advanced")
            item["group_title"] = item.get("group_title", "고급 권한")
            item["priority"] = item.get("priority", 500)
            item["advanced"] = item.get("advanced", True)
            items.append(item)

    return sorted(
        items,
        key=lambda item: (
            item.get("risk") != "high",
            int(item.get("priority", 999)),
            str(item.get("title", "")),
        ),
    )


def set_permission(permission_id: str, granted: bool) -> None:
    granted_permissions = set(config_store.get("granted_permissions", []))
    if granted:
        granted_permissions.add(permission_id)
    else:
        granted_permissions.discard(permission_id)
    config_store.set("granted_permissions", sorted(granted_permissions))
