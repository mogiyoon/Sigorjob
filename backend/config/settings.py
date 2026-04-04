import os
import sys
import platform
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List


def _app_data_dir() -> Path:
    """OS별 앱 데이터 폴더 반환. 재설치해도 DB 유지."""
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    app_dir = base / "AgentPlatform"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def _default_db_url() -> str:
    # 환경변수로 직접 지정된 경우 우선 사용 (개발 환경)
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    db_path = _app_data_dir() / "agent.db"
    return f"sqlite+aiosqlite:///{db_path}"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    database_url: str = _default_db_url()
    log_level: str = "INFO"
    allowed_shell_commands: List[str] = [
        "ls",
        "pwd",
        "echo",
        "pip",
        "npm",
        "node",
        "python3",
        "git",
        "curl",
        "wget",
        "cat",
        "grep",
        "find",
        "mkdir",
        "cp",
        "mv",
        "touch",
        "head",
        "tail",
        "wc",
        "sort",
        "uniq",
        "diff",
    ]
    allowed_directories: List[str] = [
        str(_app_data_dir()),
        "/tmp",
        str(Path.home()),
        str(_project_root()),
    ]
    # 터널 및 인증 설정
    # 개발 중에는 False, 외부 배포 시 True
    enable_tunnel: bool = False
    enable_auth: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
