from fastapi import APIRouter
from tunnel import manager as tunnel
from tunnel.pairing import get_pairing_data, rotate_token

router = APIRouter()


@router.get("/pair/data")
async def pair_data():
    """페어링 정보 반환 (QR 코드 데이터 포함). 인증 불필요."""
    if not tunnel.is_installed():
        return {
            "status": "dependency_missing",
            "tunnel_mode": tunnel.get_mode(),
            "url": None,
            "qr_data": None,
            "token": None,
            "error": (
                "cloudflared is not available. "
                "Packaged desktop builds should include it automatically. "
                "If you are running from source, install cloudflared or set CLOUDFLARED_PATH."
            ),
        }

    url = tunnel.get_url()
    if not url:
        return {
            "status": "tunnel_not_ready",
            "tunnel_mode": tunnel.get_mode(),
            "url": None,
            "qr_data": None,
            "token": None,
            "error": tunnel.get_last_error(),
        }
    data = get_pairing_data(url)
    return {"status": "ready", "tunnel_mode": tunnel.get_mode(), **data}


@router.get("/pair/status")
async def pair_status():
    """터널 상태 확인. 인증 불필요."""
    url = tunnel.get_url()
    return {
        "tunnel_active": bool(url),
        "tunnel_mode": tunnel.get_mode(),
        "url": url or None,
        "cloudflared_installed": tunnel.is_installed(),
        "tunnel_error": tunnel.get_last_error(),
    }


@router.post("/pair/rotate")
async def rotate_pair_token():
    token = rotate_token()
    return {"success": True, "token": token}
