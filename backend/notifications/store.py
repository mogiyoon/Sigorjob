import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config.settings import settings

_STORE_PATH = Path(settings.database_url.replace("sqlite+aiosqlite:///", "")).parent / "mobile_notifications.json"
_FALLBACK_PATH = Path("/tmp") / "sigorjob_mobile_notifications.json"
_LOCK = threading.Lock()


def enqueue_notification(*, title: str, body: str) -> dict:
    item = {
        "id": str(uuid.uuid4()),
        "title": title.strip() or "Sigorjob",
        "body": body.strip() or "새 알림이 도착했습니다.",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_at": None,
    }
    with _LOCK:
        data = _load()
        data.append(item)
        _save(data)
    return item


def list_unread(limit: int = 20) -> list[dict]:
    with _LOCK:
        data = _load()
        unread = [item for item in data if not item.get("read_at")]
    return unread[: max(1, min(limit, 100))]


def acknowledge(ids: list[str]) -> int:
    if not ids:
        return 0
    acknowledged = 0
    now = datetime.now(timezone.utc).isoformat()
    wanted = set(ids)
    with _LOCK:
        data = _load()
        for item in data:
            if item.get("id") in wanted and not item.get("read_at"):
                item["read_at"] = now
                acknowledged += 1
        _save(data)
    return acknowledged


def _load() -> list[dict]:
    for path in (_STORE_PATH, _FALLBACK_PATH):
        if not path.exists():
            continue
        try:
            os.chmod(path, 0o600)
        except PermissionError:
            pass
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
    return []


def _save(data: list[dict]) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    errors: list[Exception] = []
    for path in (_STORE_PATH, _FALLBACK_PATH):
        try:
            path.write_text(payload, encoding="utf-8")
            try:
                os.chmod(path, 0o600)
            except PermissionError:
                pass
            return
        except Exception as exc:
            errors.append(exc)
    if errors:
        raise errors[-1]
