from __future__ import annotations

from copy import deepcopy
from typing import Any

from config.store import config_store


Preset = dict[str, Any]


_PRESETS: list[Preset] = [
    {
        "id": "google_calendar",
        "name": "google_calendar",
        "description": "Google Calendar MCP server preset.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-google-calendar"],
    },
    {
        "id": "gmail",
        "name": "gmail",
        "description": "Gmail MCP server preset.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-gmail"],
    },
]


def _get_stored_servers() -> dict[str, Any]:
    stored = config_store.get("mcp_servers", {})
    if isinstance(stored, dict):
        return dict(stored)
    return {}


def list_presets() -> list[Preset]:
    installed_servers = _get_stored_servers()
    items: list[Preset] = []
    for preset in _PRESETS:
        item = deepcopy(preset)
        item["installed"] = item["id"] in installed_servers
        items.append(item)
    return items


def get_preset(preset_id: str) -> Preset | None:
    target = preset_id.strip()
    if not target:
        return None
    for preset in _PRESETS:
        if preset["id"] == target:
            return deepcopy(preset)
    return None


def install_preset(preset_id: str) -> dict[str, Any] | None:
    preset = get_preset(preset_id)
    if preset is None:
        return None

    stored = _get_stored_servers()
    current = stored.get(preset["id"])
    if isinstance(current, dict):
        return deepcopy(current)

    server_config = {
        "name": preset["name"],
        "transport": "stdio",
        "command": preset["command"],
        "args": list(preset["args"]),
    }
    stored[preset["id"]] = server_config
    config_store.set("mcp_servers", stored)
    return deepcopy(server_config)


def uninstall_preset(preset_id: str) -> bool | None:
    preset = get_preset(preset_id)
    if preset is None:
        return None

    stored = _get_stored_servers()
    stored.pop(preset["id"], None)
    config_store.set("mcp_servers", stored)
    return True
