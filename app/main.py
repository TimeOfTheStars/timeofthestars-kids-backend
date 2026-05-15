"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api.admin import router as admin_router
from app.api.appointments import router as appointments_router
from app.api.news_posts import router as news_router
from app.api.questions import router as questions_router
from app.api.reviews import router as reviews_router
from app.api.service_requests import router as service_requests_router
from app.api.tournament_applications import router as tournament_applications_router
from app.api.tournaments import router as tournaments_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import AsyncSessionLocal
from app.services.admin_bootstrap import bootstrap_first_admin_if_configured
from app.services.background_sync import run_periodic_vk_sync

logger = logging.getLogger(__name__)

_project_root = Path(__file__).resolve().parents[1]
_admin_static = _project_root / "static" / "admin"
_static_root = _project_root / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure logging, bootstrap admin, shared httpx client + фоновый автосинк."""
    configure_logging()
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        await bootstrap_first_admin_if_configured(session, settings)
    timeout = httpx.Timeout(settings.http_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        app.state.http_client = client

        sync_task: asyncio.Task[None] | None = None
        if settings.vk_sync_interval_minutes > 0:
            sync_task = asyncio.create_task(
                run_periodic_vk_sync(
                    settings,
                    client,
                    interval_seconds=settings.vk_sync_interval_minutes * 60,
                    initial_delay_seconds=settings.vk_sync_initial_delay_seconds,
                ),
                name="vk-auto-sync",
            )
        else:
            logger.info("VK auto-sync disabled (VK_SYNC_INTERVAL_MINUTES=0)")

        try:
            yield
        finally:
            if sync_task is not None:
                sync_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await sync_task


app = FastAPI(
    title="Time of the Stars Kids API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
async def _sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database error", extra={"path": request.url.path})
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable"},
    )


@app.get("/", tags=["meta"], include_in_schema=True)
async def root() -> dict[str, str]:
    """Корень API: подсказки вместо 404 в браузере."""
    return {
        "service": app.title,
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
        "admin_ui": "/admin/",
        "appointments": "POST /appointments",
        "service_requests": "POST /service-requests",
        "questions": "POST /questions",
        "reviews": "GET /reviews",
        "news": "GET /news",
        "tournaments": "GET /tournaments",
        "tournament_player_application": "POST /tournament-applications/player",
        "tournament_team_application": "POST /tournament-applications/team",
        "admin_api": "/api/admin",
    }


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Liveness/readiness-friendly endpoint."""
    return {"status": "ok"}


app.include_router(appointments_router)
app.include_router(service_requests_router)
app.include_router(questions_router)
app.include_router(reviews_router)
app.include_router(news_router)
app.include_router(tournaments_router)
app.include_router(tournament_applications_router)
app.include_router(admin_router, prefix="/api/admin")

if _admin_static.is_dir():
    app.mount("/admin", StaticFiles(directory=str(_admin_static), html=True), name="admin_ui")

# Загрузки (логотипы команд и т.п.) лежат в static/<subdir>/...
_static_root.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_root)), name="static")
