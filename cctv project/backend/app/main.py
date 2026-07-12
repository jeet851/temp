"""
VisionGuard — FastAPI Application Entry Point.

Creates and configures the FastAPI application with:
- CORS middleware
- Global error handling
- Request logging
- API v1 router
- WebSocket endpoint
- Background scheduler lifecycle
- Database initialization and seeding
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.middleware.cors import configure_cors
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.logging_middleware import LoggingMiddleware
from app.websocket.manager import ws_manager
from app.scheduler.tasks import start_scheduler, stop_scheduler
from app.utils.helpers import ensure_media_dirs


# ── Logging Configuration ────────────────────────────────────────────

def configure_logging() -> None:
    """Set up enterprise logging with file and console handlers."""
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    # Root logger
    root_logger = logging.getLogger("visionguard")
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

    # File handler — application log
    file_handler = logging.FileHandler(log_dir / "application.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )


# ── Application Lifespan ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown lifecycle events.

    On startup:
        1. Configure logging
        2. Create media directories
        3. Initialize database tables & seed data
        4. Start background scheduler

    On shutdown:
        1. Stop scheduler
        2. Dispose database engine
    """
    logger = logging.getLogger("visionguard")

    # ── Startup ──
    configure_logging()
    logger.info("Starting VisionGuard Backend v%s", settings.app_version)

    ensure_media_dirs()
    logger.info("Media directories verified.")

    # Create tables and seed
    from app.database.session import engine
    from app.database.base import Base
    import app.models  # noqa: F401 — register all models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified.")

    # Seed data
    from app.utils.seed import seed_database
    await seed_database()

    # Start scheduler
    start_scheduler()

    yield

    # ── Shutdown ──
    stop_scheduler()
    from app.database.session import engine as db_engine
    await db_engine.dispose()
    logger.info("VisionGuard Backend shut down gracefully.")


# ── App Factory ──────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="VisionGuard API",
        description="Enterprise Environmental Monitoring System — Backend API",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware (order matters: outermost first) ──
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(LoggingMiddleware)
    configure_cors(app)

    # ── API Routes ──
    from app.api.v1.router import api_v1_router
    app.include_router(api_v1_router, prefix="/api/v1")

    # ── WebSocket Endpoint ──
    @app.websocket("/api/v1/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                # Keep connection alive; client can send pings
                data = await websocket.receive_text()
                # Echo back for heartbeat / future commands
                if data == "ping":
                    await websocket.send_text('{"type":"pong"}')
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    # ── Static Media Files ──
    media_path = Path(settings.media_dir)
    media_path.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_path)), name="media")

    # ── Health Check ──
    @app.get("/health", tags=["System"])
    async def health_check():
        return {
            "success": True,
            "message": "VisionGuard API is running.",
            "data": {
                "version": settings.app_version,
                "environment": settings.app_env,
            },
        }

    return app


# Create the application instance
app = create_app()
