import json
import secrets
import base64
import os
from pathlib import Path
from config.settings import settings

_TOKEN_FILE = Path(settings.database_url.replace("sqlite+aiosqlite:///", "")).parent / "pair_token.txt"


def get_or_create_token() -> str:
    """페어링 토큰 반환. 없으면 생성 후 저장."""
    if _TOKEN_FILE.exists():
        try:
            os.chmod(_TOKEN_FILE, 0o600)
        except PermissionError:
            pass
        return _TOKEN_FILE.read_text().strip()
    token = secrets.token_urlsafe(32)
    _TOKEN_FILE.write_text(token)
    try:
        os.chmod(_TOKEN_FILE, 0o600)
    except PermissionError:
        pass
    return token


def verify_token(token: str) -> bool:
    return token == get_or_create_token()


def rotate_token() -> str:
    token = secrets.token_urlsafe(32)
    _TOKEN_FILE.write_text(token)
    try:
        os.chmod(_TOKEN_FILE, 0o600)
    except PermissionError:
        pass
    return token


def get_pairing_data(tunnel_url: str) -> dict:
    """QR 코드에 인코딩할 페어링 데이터 반환."""
    token = get_or_create_token()
    payload = json.dumps({"url": tunnel_url, "token": token})
    # base64 인코딩 (QR 코드 생성에 사용)
    encoded = base64.urlsafe_b64encode(payload.encode()).decode()
    return {
        "url": tunnel_url,
        "token": token,
        "qr_data": encoded,
        "raw": payload,
    }
