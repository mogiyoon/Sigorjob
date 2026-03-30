from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime, timezone
from ai.runtime import has_api_key, validate_connection
from tunnel import manager as tunnel
from config.store import config_store
from config.secret_store import secret_store
from permissions import list_permissions, set_permission

router = APIRouter()


class SetupRequest(BaseModel):
    cloudflare_tunnel_token: str


class AISetupRequest(BaseModel):
    anthropic_api_key: str


class PermissionUpdateRequest(BaseModel):
    permission_id: str
    granted: bool


def _effective_tunnel_mode() -> str:
    mode = config_store.get("tunnel_mode", "none")
    token = config_store.get("cloudflare_tunnel_token")
    if mode == "none" and token:
        return "cloudflare"
    return mode


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
        "permissions": list_permissions(
            ai_configured=ai_ready,
            tunnel_configured=mode in {"quick", "cloudflare"},
        ),
    }


@router.post("/setup/permissions")
async def update_permission(req: PermissionUpdateRequest):
    permission_id = req.permission_id.strip()
    if not permission_id:
        return {"success": False, "error": "permission_id is required"}
    set_permission(permission_id, req.granted)
    return {"success": True, "permission_id": permission_id, "granted": req.granted}


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
    import asyncio

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
    asyncio.create_task(tunnel.start())

    # 최대 15초 대기하며 URL 확인
    for _ in range(15):
        await asyncio.sleep(1)
        url = tunnel.get_url()
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
    import asyncio

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
    asyncio.create_task(tunnel.start())

    for _ in range(15):
        await asyncio.sleep(1)
        url = tunnel.get_url()
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
