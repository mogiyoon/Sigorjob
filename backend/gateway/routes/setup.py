from datetime import datetime, timezone
import subprocess
import sys

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ai.runtime import has_api_key, validate_connection
from tunnel import manager as tunnel
from connections import oauth
from connections.mcp_presets import install_preset, list_presets, uninstall_preset
from connections.oauth_scopes import get_scopes_for_connection
from connections.registry import (
    delete_custom_connection,
    get_connection,
    list_connections,
    update_external_connection,
    upsert_custom_connection,
)
from config.store import config_store
from config.secret_store import secret_store
from main import check_playwright_status
from permissions import list_permissions, set_permission

router = APIRouter()


class SetupRequest(BaseModel):
    cloudflare_tunnel_token: str


class AISetupRequest(BaseModel):
    anthropic_api_key: str


class PermissionUpdateRequest(BaseModel):
    permission_id: str
    granted: bool


class ConnectionUpdateRequest(BaseModel):
    configured: bool | None = None
    verified: bool | None = None
    account_label: str | None = None
    available: bool | None = None
    metadata: dict | None = None


class CustomConnectionRequest(BaseModel):
    connection_id: str
    title: str
    description: str | None = None
    provider: str | None = None
    auth_type: str | None = None
    driver_id: str | None = None
    capabilities: list[str] | None = None
    capability_permissions: dict | None = None
    configured: bool | None = None
    verified: bool | None = None
    account_label: str | None = None
    available: bool | None = None
    metadata: dict | None = None


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


def _effective_tunnel_mode() -> str:
    mode = config_store.get("tunnel_mode", "none")
    token = config_store.get("cloudflare_tunnel_token")
    if mode == "none" and token:
        return "cloudflare"
    return mode


def _get_supported_oauth_connection(connection_id: str) -> list[str]:
    connection = get_connection(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Unknown connection.")
    scopes = get_scopes_for_connection(connection_id)
    if not scopes:
        raise HTTPException(status_code=404, detail="OAuth is not supported for this connection.")
    return scopes


@router.get("/setup/status")
async def setup_status():
    """설정 완료 여부 및 터널 상태 반환."""
    mode = _effective_tunnel_mode()
    tunnel_url = tunnel.get_url()
    ai_ready = has_api_key()
    ai_verified = bool(config_store.get("ai_verified", False)) if ai_ready else False
    ai_validation_error = config_store.get("ai_validation_error") if ai_ready else None
    ai_verified_at = config_store.get("ai_verified_at") if ai_ready else None
    return {
        "configured": mode in {"quick", "cloudflare"},
        "tunnel_mode": mode,
        "tunnel_active": bool(tunnel_url),
        "tunnel_url": tunnel_url or None,
        "cloudflared_installed": tunnel.is_installed(),
        "cloudflared_path": tunnel.get_cloudflared_path(),
        "tunnel_error": tunnel.get_last_error(),
        "ai_configured": ai_ready,
        "ai_verified": ai_verified,
        "ai_validation_error": ai_validation_error,
        "ai_verified_at": ai_verified_at,
        "ai_storage_backend": secret_store.backend("anthropic_api_key"),
        "playwright": check_playwright_status(),
        "connections": list_connections(),
        "permissions": list_permissions(
            ai_configured=ai_ready,
            tunnel_configured=mode in {"quick", "cloudflare"},
        ),
    }


@router.get("/setup/connections")
async def get_connections():
    return {"connections": list_connections()}


@router.get("/setup/mcp/presets")
async def get_mcp_presets():
    return {"presets": list_presets()}


@router.post("/setup/mcp/presets/{preset_id}/install")
async def install_mcp_preset(preset_id: str):
    config = install_preset(preset_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Unknown MCP preset.")
    return {"success": True, "server": config}


@router.post("/setup/mcp/presets/{preset_id}/uninstall")
async def uninstall_mcp_preset(preset_id: str):
    removed = uninstall_preset(preset_id)
    if removed is None:
        raise HTTPException(status_code=404, detail="Unknown MCP preset.")
    return {"success": True, "preset_id": preset_id}


@router.post("/setup/connections/{connection_id}")
async def update_connection(connection_id: str, req: ConnectionUpdateRequest):
    if connection_id in {"mobile_connection", "anthropic_ai"}:
        return {
            "success": False,
            "error": "Core connections are managed by the app runtime.",
        }
    item = update_external_connection(
        connection_id,
        configured=req.configured,
        verified=req.verified,
        account_label=req.account_label,
        available=req.available,
        metadata=req.metadata,
    )
    if item is None:
        return {"success": False, "error": "Unknown connection."}
    return {"success": True, "connection": item}


@router.post("/setup/connections/{connection_id}/authorize")
async def authorize_connection(connection_id: str):
    scopes = _get_supported_oauth_connection(connection_id)
    result = oauth.build_google_authorize_url(connection_id, scopes)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"] or "Failed to create authorization URL.")
    data = result["data"] or {}
    return {"success": True, "auth_url": data.get("auth_url")}


@router.post("/setup/connections/{connection_id}/callback")
async def oauth_callback(connection_id: str, req: OAuthCallbackRequest):
    _get_supported_oauth_connection(connection_id)
    if not oauth.consume_authorization_state(connection_id, req.state.strip()):
        raise HTTPException(status_code=400, detail="Invalid or expired oauth state.")

    result = await oauth.exchange_code_for_tokens(connection_id, req.code)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"] or "Failed to exchange oauth code.")

    item = update_external_connection(
        connection_id,
        configured=True,
        verified=True,
        available=True,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Unknown connection.")
    return {"success": True, "connection": item}


@router.post("/setup/connections/{connection_id}/disconnect")
async def disconnect_connection(connection_id: str):
    _get_supported_oauth_connection(connection_id)
    success, error = oauth.delete_stored_tokens(connection_id)
    if not success:
        raise HTTPException(status_code=400, detail=error or "Failed to remove oauth token.")

    item = update_external_connection(
        connection_id,
        configured=False,
        verified=False,
        available=False,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Unknown connection.")
    return {"success": True, "connection": item}


@router.post("/setup/connections/custom")
async def upsert_connection(req: CustomConnectionRequest):
    item = upsert_custom_connection(
        req.connection_id,
        title=req.title.strip(),
        description=req.description,
        provider=req.provider,
        auth_type=req.auth_type,
        driver_id=req.driver_id,
        capabilities=req.capabilities,
        capability_permissions=req.capability_permissions,
        configured=req.configured,
        verified=req.verified,
        account_label=req.account_label,
        available=req.available,
        metadata=req.metadata,
    )
    if item is None:
        return {"success": False, "error": "connection_id is required"}
    return {"success": True, "connection": item}


@router.delete("/setup/connections/custom/{connection_id}")
async def remove_custom_connection(connection_id: str):
    deleted = delete_custom_connection(connection_id)
    if not deleted:
        return {"success": False, "error": "Unknown custom connection."}
    return {"success": True, "connection_id": connection_id}


@router.post("/setup/permissions")
async def update_permission(req: PermissionUpdateRequest):
    permission_id = req.permission_id.strip()
    if not permission_id:
        return {"success": False, "error": "permission_id is required"}
    set_permission(permission_id, req.granted)
    return {"success": True, "permission_id": permission_id, "granted": req.granted}


@router.post("/setup/playwright/install")
async def install_playwright():
    pip_result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "playwright"],
        capture_output=True,
        text=True,
        check=False,
    )
    if pip_result.returncode != 0:
        return {
            "success": False,
            "error": (pip_result.stderr or pip_result.stdout or "pip install playwright failed").strip(),
            "risk_level": "medium",
        }

    browser_result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
        check=False,
    )
    if browser_result.returncode != 0:
        return {
            "success": False,
            "error": (browser_result.stderr or browser_result.stdout or "playwright install chromium failed").strip(),
            "risk_level": "medium",
        }

    return {"success": True, "risk_level": "medium"}


@router.post("/setup/ai")
async def setup_ai(req: AISetupRequest):
    api_key = req.anthropic_api_key.strip()
    if not api_key:
        return {"success": False, "error": "API key is required."}

    success, error = secret_store.set("anthropic_api_key", api_key)
    if not success:
        return {"success": False, "error": error or "Failed to store API key securely."}

    verified, validation_error = validate_connection()
    config_store.set("ai_verified", verified)
    config_store.set("ai_validation_error", validation_error)
    config_store.set(
        "ai_verified_at",
        datetime.now(timezone.utc).isoformat() if verified else None,
    )
    return {
        "success": True,
        "configured": True,
        "verified": verified,
        "validation_error": validation_error,
        "storage_backend": secret_store.backend("anthropic_api_key"),
    }


@router.post("/setup/ai/verify")
async def verify_ai():
    if not has_api_key():
        return {"success": False, "error": "API key is not configured.", "verified": False}

    verified, validation_error = validate_connection()
    config_store.set("ai_verified", verified)
    config_store.set("ai_validation_error", validation_error)
    config_store.set(
        "ai_verified_at",
        datetime.now(timezone.utc).isoformat() if verified else None,
    )
    return {
        "success": verified,
        "verified": verified,
        "validation_error": validation_error,
    }


@router.delete("/setup/ai")
async def reset_ai():
    success, error = secret_store.delete("anthropic_api_key")
    if not success:
        return {"success": False, "error": error or "Failed to remove stored API key."}
    config_store.delete("ai_verified")
    config_store.delete("ai_validation_error")
    config_store.delete("ai_verified_at")
    return {"success": True, "configured": False}


@router.post("/setup/cloudflare")
async def setup_cloudflare(req: SetupRequest):
    """Cloudflare 터널 토큰 저장 후 터널 연결 시도."""
    if not tunnel.is_installed():
        return {
            "success": False,
            "tunnel_url": None,
            "error": (
                "cloudflared is not available. "
                "Packaged desktop builds should include it automatically. "
                "If you are running from source, install cloudflared or set CLOUDFLARED_PATH."
            ),
        }

    config_store.set("tunnel_mode", "cloudflare")
    config_store.set("cloudflare_tunnel_token", req.cloudflare_tunnel_token)

    # 기존 터널 종료 후 재시작
    await tunnel.stop()
    url = await tunnel.start()
    if url:
        return {"success": True, "tunnel_url": url}

    return {
        "success": False,
        "tunnel_url": None,
        "error": tunnel.get_last_error() or "터널 연결 시간 초과. 토큰을 확인해주세요.",
    }


@router.post("/setup/quick")
async def setup_quick_tunnel():
    """Quick Tunnel 모드 활성화."""
    if not tunnel.is_installed():
        return {
            "success": False,
            "tunnel_url": None,
            "error": (
                "cloudflared is not available. "
                "Packaged desktop builds should include it automatically. "
                "If you are running from source, install cloudflared or set CLOUDFLARED_PATH."
            ),
        }

    config_store.set("tunnel_mode", "quick")
    config_store.delete("cloudflare_tunnel_token")

    await tunnel.stop()
    url = await tunnel.start()
    if url:
        return {"success": True, "tunnel_url": url}

    return {
        "success": False,
        "tunnel_url": None,
        "error": tunnel.get_last_error() or "Quick Tunnel 연결 시간 초과. 잠시 후 다시 시도해주세요.",
    }


@router.delete("/setup/cloudflare")
async def reset_cloudflare():
    """터널 토큰 초기화."""
    config_store.set("tunnel_mode", "none")
    config_store.delete("cloudflare_tunnel_token")
    await tunnel.stop()
    return {"success": True}


@router.delete("/setup/tunnel")
async def disconnect_tunnel():
    """현재 활성화된 터널 연결 해제."""
    config_store.set("tunnel_mode", "none")
    config_store.delete("cloudflare_tunnel_token")
    await tunnel.stop()
    return {"success": True, "configured": False, "tunnel_url": None}
