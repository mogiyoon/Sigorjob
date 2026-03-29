import re
import yaml
from pathlib import Path
from logger.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

_policies: dict = {}


def _resolve_path(path: str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _is_under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _is_allowed_directory(path: Path) -> bool:
    for allowed_dir in settings.allowed_directories:
        allowed_root = _resolve_path(allowed_dir)
        if _is_under(path, allowed_root):
            return True
    return False


def _is_protected_internal_path(path: Path) -> bool:
    db_path = Path(settings.database_url.replace("sqlite+aiosqlite:///", "")).resolve(strict=False)
    protected = {
        db_path,
        db_path.parent / "config.json",
        db_path.parent / "pair_token.txt",
    }
    return path in protected


def load_policies():
    global _policies
    path = Path(__file__).parent / "policies.yaml"
    with open(path) as f:
        _policies = yaml.safe_load(f)


def check_shell(command: str) -> tuple[bool, str]:
    """쉘 명령 허용 여부 반환. (allowed, reason)"""
    if not _policies:
        load_policies()

    cmd_base = command.strip().split()[0]
    blocked = _policies.get("shell", {}).get("blocked_commands", [])
    if cmd_base in blocked:
        return False, f"blocked command: {cmd_base}"

    patterns = _policies.get("shell", {}).get("blocked_patterns", [])
    for pattern in patterns:
        if re.search(pattern, command):
            return False, f"blocked pattern: {pattern}"

    return True, ""


def check_file(path: str, operation: str = "read") -> tuple[bool, str]:
    """파일 접근 허용 여부 반환. (allowed, reason)"""
    if not _policies:
        load_policies()

    resolved = _resolve_path(path)
    if not _is_allowed_directory(resolved):
        return False, f"path outside allowed directories: {resolved}"

    if _is_protected_internal_path(resolved):
        return False, "access to internal app data is blocked"

    if operation == "read":
        ext = resolved.suffix
        blocked_ext = _policies.get("file", {}).get("blocked_extensions", [])
        if ext in blocked_ext:
            return False, f"blocked file extension: {ext}"

    if operation in {"write", "copy_dst", "move_dst", "delete"}:
        approval_paths = _policies.get("file", {}).get("require_approval_paths", [])
        for ap in approval_paths:
            protected_root = _resolve_path(ap)
            if _is_under(resolved, protected_root):
                return False, f"{operation} on protected path requires approval: {ap}"

    return True, ""


def get_risk_level(action: str) -> str:
    if not _policies:
        load_policies()
    return _policies.get("risk_levels", {}).get(action, "low")
