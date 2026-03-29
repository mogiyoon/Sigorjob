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
    },
    {
        "id": "ai_fallback_access",
        "title": "AI fallback",
        "description": "비AI 처리로 부족한 경우 AI가 계획과 요약을 돕습니다.",
        "source": "core",
        "required_for": ["ai_planning", "ai_review"],
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
        items.append(permission)

    for plugin in describe_plugins():
        for permission in plugin.get("permissions", []):
            item = dict(permission)
            item["source"] = plugin["name"]
            item["granted"] = item["id"] in granted_permissions
            item["risk"] = item.get("risk", "low")
            items.append(item)

    return items


def set_permission(permission_id: str, granted: bool) -> None:
    granted_permissions = set(config_store.get("granted_permissions", []))
    if granted:
        granted_permissions.add(permission_id)
    else:
        granted_permissions.discard(permission_id)
    config_store.set("granted_permissions", sorted(granted_permissions))
