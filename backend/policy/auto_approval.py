import hashlib
import json
from datetime import datetime, timezone

from config.store import config_store

_STORE_KEY = "auto_approval_patterns"


def _load_patterns() -> list[dict]:
    stored = config_store.get(_STORE_KEY, [])
    if not isinstance(stored, list):
        return []
    return [item for item in stored if isinstance(item, dict)]


def _save_patterns(patterns: list[dict]) -> None:
    config_store.set(_STORE_KEY, patterns)


def params_hash(params: dict) -> str:
    payload = json.dumps(params or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def pattern_id(tool: str, params: dict) -> str:
    return f"{tool}:{params_hash(params)}"


def find_pattern(tool: str, params: dict) -> dict | None:
    target_hash = params_hash(params)
    for item in _load_patterns():
        if item.get("tool") == tool and item.get("pattern_hash") == target_hash:
            return item
    return None


def is_auto_approved(tool: str, params: dict) -> bool:
    return find_pattern(tool, params) is not None


def record_approved_pattern(tool: str, params: dict) -> dict:
    patterns = _load_patterns()
    target_hash = params_hash(params)
    approved_at = datetime.now(timezone.utc).isoformat()

    for item in patterns:
        if item.get("tool") == tool and item.get("pattern_hash") == target_hash:
            item["approved_at"] = approved_at
            item["count"] = int(item.get("count", 0)) + 1
            _save_patterns(patterns)
            return item

    entry = {
        "id": f"{tool}:{target_hash}",
        "tool": tool,
        "pattern_hash": target_hash,
        "approved_at": approved_at,
        "count": 1,
    }
    patterns.append(entry)
    _save_patterns(patterns)
    return entry


def list_patterns() -> list[dict]:
    return _load_patterns()


def remove_pattern(pattern_id_value: str) -> bool:
    patterns = _load_patterns()
    filtered = [item for item in patterns if item.get("id") != pattern_id_value]
    if len(filtered) == len(patterns):
        return False
    _save_patterns(filtered)
    return True
