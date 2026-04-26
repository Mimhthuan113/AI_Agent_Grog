"""
FastAPI Application Factory
=============================
Tạo và cấu hình FastAPI app instance.

Tách riêng app factory để:
- Dễ test (tạo nhiều app instance với config khác nhau)
- Clean separation of concerns
- Tuân thủ 12-Factor App methodology

Usage:
    uvicorn src.api.app:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.config import get_settings
from src.api.routes.health import router as health_router
from src.api.routes.auth import router as auth_router
from src.api.routes.chat import router as chat_router
from src.api.routes.voice import router as voice_router
from src.api.routes.monitor import router as monitor_router
from src.api.routes.apps import router as apps_router
from src.api.routes.users import router as users_router

# ── Logging Setup ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context — modern FastAPI startup/shutdown (thay cho on_event).
    Dùng để init shared resources (HA client, DB pool, ...) và cleanup.
    """
    settings = get_settings()

    # ── Startup ──────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Smart AI Home Hub — Starting up...")
    logger.info("Environment: %s", settings.app_env)
    logger.info("Debug mode: %s", settings.app_debug)
    logger.info("CORS origins: %s", settings.cors_origins_list)
    logger.info("JWT Algorithm: %s", settings.jwt_algorithm)
    logger.info("Token expiry: %d minutes", settings.jwt_access_token_expire_minutes)
    logger.info("Groq model: %s", settings.groq_model_default)
    logger.info("=" * 60)

    # Init audit DB (lazy ensure schema + WAL mode)
    try:
        from src.core.security.audit_logger import get_audit_logger
        await get_audit_logger().init()
    except Exception as e:
        logger.error("[STARTUP] Audit init failed: %s", str(e)[:200])

    # Init HA client (chỉ khi có HA_TOKEN — nếu không thì gateway dùng mock)
    if settings.ha_token:
        try:
            from src.services.ha_provider.ha_client import get_ha_client
            from src.core.security.gateway import get_gateway
            ha = await get_ha_client()
            get_gateway().set_ha_client(ha)
            logger.info("[STARTUP] HA client connected: %s", settings.ha_base_url)
        except Exception as e:
            logger.warning("[STARTUP] HA client unavailable, fallback mock: %s", str(e)[:200])

    yield  # ← App đang chạy ở đây

    # ── Shutdown ─────────────────────────────────────────
    logger.info("Smart AI Home Hub — Shutting down...")
    try:
        from src.services.ha_provider.ha_client import close_ha_client
        await close_ha_client()
    except Exception:
        pass


def create_app() -> FastAPI:
    """
    Application Factory Pattern.
    Tạo FastAPI instance với đầy đủ middleware và routes.
    """
    settings = get_settings()

    # ── Create FastAPI app ─────────────────────────────────
    app = FastAPI(
        title="Smart AI Home Hub",
        description=(
            "Hệ thống điều khiển nhà thông minh tích hợp AI "
            "với kiến trúc Zero Trust Security"
        ),
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── CORS Middleware ────────────────────────────────────
    cors_origins = settings.cors_origins_list
    if not settings.is_production:
        cors_origins = ["*"]  # Dev mode: cho phep moi origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # ── Register Routes ────────────────────────────────────
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(voice_router)
    app.include_router(monitor_router)
    app.include_router(apps_router)
    app.include_router(users_router)

    # ── Static Files (Frontend) ────────────────────────────
    static_dir = Path(__file__).parent.parent.parent / "static"
    if static_dir.exists():
        @app.get("/", include_in_schema=False)
        async def serve_index():
            return FileResponse(static_dir / "index.html")
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info("Static files served from: %s", static_dir)

    return app


# ── App Instance (cho uvicorn) ─────────────────────────────
app = create_app()
