from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config.secret_store import secret_store
from config.store import config_store


_TOKEN_KEY_PREFIX = "google_oauth_tokens:"
_DEFAULT_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _token_key(connection_id: str) -> str:
    return f"{_TOKEN_KEY_PREFIX}{connection_id}"


def _google_oauth_config() -> tuple[str, str, str]:
    client_id = str(config_store.get("google_oauth_client_id", "") or "").strip()
    client_secret = str(config_store.get("google_oauth_client_secret", "") or "").strip()
    redirect_uri = str(config_store.get("google_oauth_redirect_uri", "") or "").strip()
    return client_id, client_secret, redirect_uri


def _normalize_token_payload(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    current = dict(existing or {})
    normalized = dict(payload)
    if "refresh_token" not in normalized and current.get("refresh_token"):
        normalized["refresh_token"] = current["refresh_token"]
    expires_in = normalized.get("expires_in")
    if isinstance(expires_in, (int, float)):
        normalized["expires_at"] = int(time.time() + int(expires_in))
    elif isinstance(expires_in, str) and expires_in.isdigit():
        normalized["expires_at"] = int(time.time() + int(expires_in))
    return normalized


def _load_tokens(connection_id: str) -> dict[str, Any] | None:
    raw = secret_store.get(_token_key(connection_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return data
    return None


def _save_tokens(connection_id: str, tokens: dict[str, Any]) -> tuple[bool, str | None]:
    return secret_store.set(_token_key(connection_id), json.dumps(tokens))


def get_stored_tokens(connection_id: str) -> dict[str, Any] | None:
    return _load_tokens(connection_id)


async def store_tokens(connection_id: str, tokens: dict[str, Any]) -> tuple[bool, str | None]:
    normalized = _normalize_token_payload(tokens, _load_tokens(connection_id))
    return await asyncio.get_running_loop().run_in_executor(None, _save_tokens, connection_id, normalized)


def _post_form_sync(url: str, data: dict[str, Any]) -> dict[str, Any]:
    body = urlencode(data).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw or "{}")
    if not isinstance(parsed, dict):
        raise ValueError("oauth token response must be a JSON object")
    return parsed


async def _post_form(url: str, data: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.get_running_loop().run_in_executor(None, _post_form_sync, url, data)


async def exchange_code_for_tokens(
    connection_id: str,
    code: str,
    *,
    token_url: str = _DEFAULT_TOKEN_URL,
) -> dict[str, Any]:
    client_id, client_secret, redirect_uri = _google_oauth_config()
    if not client_id or not client_secret or not redirect_uri:
        return {"success": False, "data": None, "error": "google oauth config is incomplete"}
    if not code.strip():
        return {"success": False, "data": None, "error": "authorization code is required"}

    try:
        payload = await _post_form(
            token_url,
            {
                "code": code.strip(),
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return {"success": False, "data": None, "error": str(exc)}

    if not payload.get("access_token"):
        return {"success": False, "data": None, "error": "oauth token response did not include access_token"}

    normalized = _normalize_token_payload(payload)
    ok, error = await store_tokens(connection_id, normalized)
    if not ok:
        return {"success": False, "data": None, "error": error or "failed to store oauth token"}
    return {"success": True, "data": normalized, "error": None}


async def refresh_access_token(
    connection_id: str,
    *,
    token_url: str = _DEFAULT_TOKEN_URL,
) -> dict[str, Any]:
    current = _load_tokens(connection_id) or {}
    refresh_token = str(current.get("refresh_token") or "").strip()
    client_id, client_secret, _redirect_uri = _google_oauth_config()
    if not client_id or not client_secret:
        return {"success": False, "data": None, "error": "google oauth config is incomplete"}
    if not refresh_token:
        return {"success": False, "data": None, "error": "refresh token is missing"}

    try:
        payload = await _post_form(
            token_url,
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return {"success": False, "data": None, "error": str(exc)}

    if not payload.get("access_token"):
        return {"success": False, "data": None, "error": "oauth refresh response did not include access_token"}

    normalized = _normalize_token_payload(payload, current)
    ok, error = await store_tokens(connection_id, normalized)
    if not ok:
        return {"success": False, "data": None, "error": error or "failed to store oauth token"}
    return {"success": True, "data": normalized, "error": None}


async def get_access_token(connection_id: str) -> str | None:
    tokens = _load_tokens(connection_id)
    if not tokens:
        return None

    access_token = str(tokens.get("access_token") or "").strip()
    expires_at = tokens.get("expires_at")
    if access_token and (not isinstance(expires_at, int) or expires_at > int(time.time()) + 30):
        return access_token

    refresh_result = await refresh_access_token(connection_id)
    if not refresh_result["success"]:
        return access_token or None
    refreshed = refresh_result.get("data") or {}
    return str(refreshed.get("access_token") or "").strip() or None
