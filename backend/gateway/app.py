import asyncio
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from db.session import init_db
from tools.registry import load_default_tools
from plugins import load_plugins
from gateway.routes.command import router as command_router
from gateway.routes.pair import router as pair_router
from gateway.routes.setup import router as setup_router
from gateway.routes.approval import router as approval_router
from gateway.routes.mobile_notifications import router as mobile_notifications_router
from gateway.routes.schedule import router as schedule_router
from gateway.routes.widget import router as widget_router
from gateway.middleware.auth import TokenAuthMiddleware
from tunnel import manager as tunnel
from scheduler import service as scheduler_service
from config.settings import settings
from config.store import config_store
from logger.logger import get_logger

logger = get_logger(__name__)

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
except ModuleNotFoundError:
    Limiter = None
    _rate_limit_exceeded_handler = None
    get_remote_address = None
    RateLimitExceeded = None
    logger.warning("slowapi is not installed; rate limiting is disabled.")

limiter = (
    Limiter(key_func=get_remote_address, default_limits=["60/minute"])
    if Limiter and get_remote_address
    else None
)


def _frontend_dist() -> Path | None:
    """Next.js 빌드 결과 경로. 번들 내부 → 상대경로 순으로 탐색."""
    if getattr(sys, "frozen", False):
        # PyInstaller 번들
        candidate = Path(sys._MEIPASS) / "frontend_out"
        if candidate.exists():
            return candidate
    # 개발 환경: backend/ 기준 ../frontend/out
    candidate = Path(__file__).parent.parent.parent / "frontend" / "out"
    if candidate.exists():
        return candidate
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    load_default_tools()
    load_plugins()
    await scheduler_service.start()
    tunnel_mode = config_store.get("tunnel_mode", "none")
    if tunnel_mode == "none" and config_store.get("cloudflare_tunnel_token"):
        tunnel_mode = "cloudflare"
        config_store.set("tunnel_mode", tunnel_mode)
    if tunnel_mode in {"quick", "cloudflare"}:
        asyncio.create_task(tunnel.start())
    yield
    await scheduler_service.stop()
    await tunnel.stop()


app = FastAPI(title="Sigorjob", lifespan=lifespan)

app.state.limiter = limiter
if limiter and RateLimitExceeded and _rate_limit_exceeded_handler:
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^(?:tauri://localhost|https?://(?:localhost|127\.0\.0\.1)(?::\d+)?)$",
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.enable_auth:
    app.add_middleware(TokenAuthMiddleware)

# API 라우터 (정적 파일보다 먼저 등록)
app.include_router(setup_router)
app.include_router(pair_router)
app.include_router(command_router)
app.include_router(approval_router)
app.include_router(mobile_notifications_router)
app.include_router(schedule_router)
app.include_router(widget_router)


@app.get("/tools")
async def list_tools():
    from tools import registry
    return {"tools": registry.list_tools()}


# Next.js 정적 파일 서빙 (모바일 WebView용)
# `next build`로 생성된 out/ 디렉토리를 서빙
_dist = _frontend_dist()
if _dist:
    app.mount("/_next", StaticFiles(directory=str(_dist / "_next")), name="next_assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Next.js static export SPA 라우팅."""
        dist = _frontend_dist()
        if not dist:
            return {"error": "frontend not built"}
        # 정확한 파일이 있으면 반환
        target = dist / full_path
        if target.is_file():
            return FileResponse(target)
        html_file = dist / f"{full_path}.html"
        if html_file.exists():
            return FileResponse(html_file)
        # HTML 파일 탐색 (Next.js static export 규칙)
        html = dist / full_path / "index.html"
        if html.exists():
            return FileResponse(html)
        # fallback: index.html
        return FileResponse(dist / "index.html")
