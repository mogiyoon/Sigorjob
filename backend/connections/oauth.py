from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config.secret_store import secret_store
from config.store import config_store


_TOKEN_KEY_PREFIX = "google_oauth_tokens:"
_DEFAULT_TOKEN_URL = "https://oauth2.googleapis.com/token"
_DEFAULT_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_STATE_TTL_SECONDS = 600
_oauth_states: dict[str, dict[str, Any]] = {}


def _token_key(connection_id: str) -> str:
    return f"{_TOKEN_KEY_PREFIX}{connection_id}"


def _google_oauth_config() -> tuple[str, str, str]:
    client_id = str(config_store.get("google_oauth_client_id", "") or "").strip()
    client_secret = str(config_store.get("google_oauth_client_secret", "") or "").strip()
    redirect_uri = str(config_store.get("google_oauth_redirect_uri", "") or "").strip()
    return client_id, client_secret, redirect_uri


def _now() -> int:
    return int(time.time())


def _prune_expired_states(now: int | None = None) -> None:
    current_time = _now() if now is None else now
    expired = [
        state
        for state, payload in _oauth_states.items()
        if int(payload.get("expires_at", 0)) <= current_time
    ]
    for state in expired:
        _oauth_states.pop(state, None)


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


def delete_stored_tokens(connection_id: str) -> tuple[bool, str | None]:
    return secret_store.delete(_token_key(connection_id))


def get_stored_tokens(connection_id: str) -> dict[str, Any] | None:
    return _load_tokens(connection_id)


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(96).rstrip("=")
    if len(verifier) < 43:
        verifier = f"{verifier}{'A' * (43 - len(verifier))}"
    verifier = verifier[:128]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    return verifier, challenge


def create_authorization_state(connection_id: str, code_verifier: str | None = None) -> str:
    _prune_expired_states()
    state = secrets.token_urlsafe(32)
    now = _now()
    payload: dict[str, Any] = {
        "connection_id": connection_id,
        "created_at": now,
        "expires_at": now + _STATE_TTL_SECONDS,
    }
    if code_verifier:
        payload["code_verifier"] = code_verifier
    _oauth_states[state] = payload
    return state


def consume_authorization_state(connection_id: str, state: str) -> dict[str, Any] | None:
    _prune_expired_states()
    payload = _oauth_states.get(state)
    if not payload:
        return None
    if payload.get("connection_id") != connection_id:
        return None
    if int(payload.get("expires_at", 0)) <= _now():
        _oauth_states.pop(state, None)
        return None
    return _oauth_states.pop(state, None)


def build_google_authorize_url(connection_id: str, scopes: list[str]) -> dict[str, Any]:
    client_id, _client_secret, redirect_uri = _google_oauth_config()
    if not client_id or not redirect_uri:
        return {"success": False, "data": None, "error": "google oauth config is incomplete"}
    if not scopes:
        return {"success": False, "data": None, "error": "oauth scopes are not configured"}

    code_verifier, code_challenge = generate_pkce_pair()
    state = create_authorization_state(connection_id, code_verifier)
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return {
        "success": True,
        "data": {
            "auth_url": f"{_DEFAULT_AUTHORIZE_URL}?{query}",
            "state": state,
        },
        "error": None,
    }


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
    code_verifier: str | None = None,
    token_url: str = _DEFAULT_TOKEN_URL,
) -> dict[str, Any]:
    client_id, _client_secret, redirect_uri = _google_oauth_config()
    if not client_id or not redirect_uri:
        return {"success": False, "data": None, "error": "google oauth config is incomplete"}
    if not code.strip():
        return {"success": False, "data": None, "error": "authorization code is required"}

    request_data = {
        "code": code.strip(),
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    if code_verifier:
        request_data["code_verifier"] = code_verifier.strip()

    try:
        payload = await _post_form(token_url, request_data)
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
    client_id, _client_secret, _redirect_uri = _google_oauth_config()
    if not client_id:
        return {"success": False, "data": None, "error": "google oauth config is incomplete"}
    if not refresh_token:
        return {"success": False, "data": None, "error": "refresh token is missing"}

    try:
        payload = await _post_form(
            token_url,
            {
                "client_id": client_id,
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
