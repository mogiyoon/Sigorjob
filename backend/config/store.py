"""
앱 설정을 로컬 JSON 파일에 저장/조회하는 단순 스토어.
DB가 아닌 파일로 관리해 앱 시작 전에도 접근 가능하도록 함.
"""
import json
import os
from pathlib import Path
from config.settings import settings

_STORE_PATH = Path(settings.database_url.replace("sqlite+aiosqlite:///", "")).parent / "config.json"


class ConfigStore:
    def _load(self) -> dict:
        if _STORE_PATH.exists():
            try:
                _STORE_PATH.chmod(0o600)
                return json.loads(_STORE_PATH.read_text())
            except Exception:
                return {}
        return {}

    def _save(self, data: dict):
        _STORE_PATH.write_text(json.dumps(data, indent=2))
        try:
            os.chmod(_STORE_PATH, 0o600)
        except PermissionError:
            pass

    def get(self, key: str, default=None):
        return self._load().get(key, default)

    def set(self, key: str, value):
        data = self._load()
        data[key] = value
        self._save(data)

    def delete(self, key: str):
        data = self._load()
        data.pop(key, None)
        self._save(data)

    def all(self) -> dict:
        return self._load()


config_store = ConfigStore()
