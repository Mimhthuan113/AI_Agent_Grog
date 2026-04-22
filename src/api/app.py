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

# ── Logging Setup ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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

    # ── Static Files (Frontend) ────────────────────────────
    static_dir = Path(__file__).parent.parent.parent / "static"
    if static_dir.exists():
        @app.get("/", include_in_schema=False)
        async def serve_index():
            return FileResponse(static_dir / "index.html")
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info("Static files served from: %s", static_dir)

    # ── Startup Event ──────────────────────────────────────
    @app.on_event("startup")
    async def on_startup():
        logger.info("=" * 60)
        logger.info("Smart AI Home Hub — Starting up...")
        logger.info("Environment: %s", settings.app_env)
        logger.info("Debug mode: %s", settings.app_debug)
        logger.info("CORS origins: %s", settings.cors_origins_list)
        logger.info("JWT Algorithm: %s", settings.jwt_algorithm)
        logger.info("Token expiry: %d minutes", settings.jwt_access_token_expire_minutes)
        logger.info("Groq model: %s", settings.groq_model_default)
        logger.info("=" * 60)

    # ── Shutdown Event ─────────────────────────────────────
    @app.on_event("shutdown")
    async def on_shutdown():
        logger.info("Smart AI Home Hub — Shutting down...")

    return app


# ── App Instance (cho uvicorn) ─────────────────────────────
app = create_app()
