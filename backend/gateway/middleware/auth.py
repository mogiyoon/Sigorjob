import ipaddress
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# 로컬에서만 접근 가능한 경로
LOCAL_ONLY_PATHS = {
    "/pair",
    "/pair/data",
    "/pair/status",
    "/pair/rotate",
    "/setup",
    "/setup/status",
    "/setup/cloudflare",
    "/setup/quick",
    "/setup/tunnel",
    "/setup/ai",
    "/setup/permissions",
    "/mobile/notifications/test",
    "/openapi.json",
}

class TokenAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        is_local = _is_local_request(request)

        if _is_local_only_path(request.url.path) and not is_local:
            return JSONResponse(status_code=403, content={"error": "forbidden"})

        if is_local:
            return await call_next(request)

        raw_token = _extract_token(request)
        if not raw_token:
            return JSONResponse(status_code=401, content={"error": "unauthorized"})

        from tunnel.pairing import verify_token
        if not verify_token(raw_token):
            return JSONResponse(status_code=401, content={"error": "invalid token"})

        response = await call_next(request)
        if request.method == "GET" and request.query_params.get("_token"):
            response.set_cookie(
                key="agent_token",
                value=raw_token,
                httponly=True,
                secure=True,
                samesite="lax",
            )
        return response


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    cookie_token = request.cookies.get("agent_token")
    if cookie_token:
        return cookie_token
    if request.method == "GET":
        bootstrap_token = request.query_params.get("_token")
        if bootstrap_token:
            return bootstrap_token
    return request.query_params.get("token")

def _is_local_request(request: Request) -> bool:
    client = request.client.host if request.client else ""
    if not client:
        return False
    try:
        return ipaddress.ip_address(client).is_loopback
    except ValueError:
        return client in {"localhost"}


def _is_local_only_path(path: str) -> bool:
    return path in LOCAL_ONLY_PATHS or path.startswith("/docs")
