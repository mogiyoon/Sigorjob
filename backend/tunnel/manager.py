import asyncio
import os
import re
import shutil
import sys
from pathlib import Path
from logger.logger import get_logger

logger = get_logger(__name__)

_tunnel_url: str = ""
_process: asyncio.subprocess.Process | None = None
_last_error: str = ""
_tunnel_mode: str = "none"


def _cloudflared_path() -> str:
    """cloudflared 바이너리 경로 탐색. 번들 → PATH 순서."""
    env_path = os.environ.get("CLOUDFLARED_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        bundled = base / "cloudflared"
        if bundled.exists():
            return str(bundled)
        executable_dir = Path(sys.executable).resolve(strict=False).parent
        sibling = executable_dir / "cloudflared"
        if sibling.exists():
            return str(sibling)
    found = shutil.which("cloudflared")
    if found:
        return found
    raise FileNotFoundError("cloudflared not found")


def is_installed() -> bool:
    try:
        _cloudflared_path()
        return True
    except FileNotFoundError:
        return False


def get_cloudflared_path() -> str | None:
    try:
        return _cloudflared_path()
    except FileNotFoundError:
        return None


def get_last_error() -> str | None:
    return _last_error or None


def get_mode() -> str:
    return _tunnel_mode


async def start() -> str:
    """설정된 모드에 따라 Cloudflare 터널 시작."""
    global _tunnel_url, _process, _last_error, _tunnel_mode
    _last_error = ""

    try:
        binary = _cloudflared_path()
    except FileNotFoundError as e:
        _last_error = (
            "cloudflared is not available. "
            "Use a packaged desktop build, or install cloudflared / set CLOUDFLARED_PATH in source-based environments."
        )
        logger.error(str(e))
        return ""

    # 저장된 토큰 확인
    from config.store import config_store
    token = config_store.get("cloudflare_tunnel_token")
    configured_mode = config_store.get("tunnel_mode", "none")

    if configured_mode == "cloudflare":
        if not token:
            _tunnel_mode = "cloudflare"
            _last_error = "Cloudflare token mode is selected, but no tunnel token is configured."
            logger.warning(_last_error)
            return ""

        # 개인 계정 터널 (고정 URL)
        _tunnel_mode = "cloudflare"
        logger.info("Starting cloudflared with account token...")
        cmd = [binary, "tunnel", "run", "--token", token]
        url_pattern = re.compile(r"https://[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-]+\.com")
    else:
        # 임시 터널 (trycloudflare.com, 토큰 미설정 시 fallback)
        _tunnel_mode = "quick"
        logger.info("Starting cloudflared quick tunnel (no token set)...")
        cmd = [binary, "tunnel", "--url", "http://localhost:8000"]
        url_pattern = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com")

    _process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    url = await _read_tunnel_url(_process, url_pattern, timeout=20)
    if url:
        _tunnel_url = url
        _last_error = ""
        logger.info(f"Tunnel active: {url}")
    else:
        if _tunnel_mode == "cloudflare":
            _last_error = (
                "Cloudflare tunnel did not become ready. "
                "Check the tunnel token, and make sure the tunnel has a public hostname or route configured in Cloudflare."
            )
        else:
            _last_error = (
                "Quick Tunnel did not become ready within the timeout. "
                "Check the local network state and try again."
            )
        logger.warning("Tunnel URL not detected within timeout")

    return _tunnel_url


async def _read_tunnel_url(proc, pattern: re.Pattern, timeout: float) -> str:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            line = await asyncio.wait_for(proc.stderr.readline(), timeout=1.0)
            text = line.decode(errors="ignore")
            match = pattern.search(text)
            if match:
                return match.group(0)
        except asyncio.TimeoutError:
            continue
    return ""


def get_url() -> str:
    return _tunnel_url


async def stop():
    global _process, _tunnel_url, _tunnel_mode
    if _process:
        _process.terminate()
        try:
            await asyncio.wait_for(_process.wait(), timeout=3)
        except asyncio.TimeoutError:
            _process.kill()
        _process = None
        _tunnel_url = ""
        _tunnel_mode = "none"
        logger.info("Tunnel stopped")
