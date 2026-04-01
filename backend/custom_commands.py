from __future__ import annotations

import uuid

from config.store import config_store


CustomCommand = dict[str, str | bool]
_STORE_KEY = "custom_commands"


def list_custom_commands() -> list[CustomCommand]:
    items = config_store.get(_STORE_KEY, [])
    if not isinstance(items, list):
        return []
    normalized: list[CustomCommand] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "id": str(item.get("id") or str(uuid.uuid4())),
                "trigger": str(item.get("trigger") or "").strip(),
                "match_type": str(item.get("match_type") or "contains").strip(),
                "action_text": str(item.get("action_text") or "").strip(),
                "enabled": bool(item.get("enabled", True)),
            }
        )
    return normalized


def create_custom_command(trigger: str, action_text: str, *, match_type: str = "contains") -> CustomCommand:
    item: CustomCommand = {
        "id": str(uuid.uuid4()),
        "trigger": trigger.strip(),
        "match_type": "exact" if match_type == "exact" else "contains",
        "action_text": action_text.strip(),
        "enabled": True,
    }
    items = list_custom_commands()
    items.append(item)
    config_store.set(_STORE_KEY, items)
    return item


def delete_custom_command(rule_id: str) -> bool:
    items = list_custom_commands()
    filtered = [item for item in items if item["id"] != rule_id]
    if len(filtered) == len(items):
        return False
    config_store.set(_STORE_KEY, filtered)
    return True


def match_custom_command(command: str) -> CustomCommand | None:
    text = command.strip().lower()
    if not text:
        return None
    for item in list_custom_commands():
        if not item.get("enabled"):
            continue
        trigger = str(item.get("trigger") or "").strip().lower()
        if not trigger:
            continue
        if item.get("match_type") == "exact":
            if text == trigger:
                return item
            continue
        if trigger in text:
            return item
    return None
