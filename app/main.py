"""
TelcoPulse - FastAPI Application Entry Point
Wires together database initialisation, rate limiting, routers, and the
background monitoring scheduler via the ASGI lifespan protocol.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import engine, Base
from app.api import targets, health
from app.services.scheduler import start_scheduler, stop_scheduler

logger = get_logger(__name__)
settings = get_settings()


# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"])


# ── Database initialisation ───────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables if they don't exist. In production, prefer Alembic migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified / created.")


# ── Application lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic managed via the modern ASGI lifespan."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} …")

    # Import models so SQLAlchemy registers them with Base.metadata
    import app.models.target      # noqa: F401
    import app.models.check_log   # noqa: F401

    await init_db()
    start_scheduler()

    logger.info(f"{settings.APP_NAME} is ready.")
    yield  # ── application runs here ──────────────────────────────────────────

    logger.info("Shutting down …")
    stop_scheduler()
    await engine.dispose()
    logger.info("Shutdown complete.")


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-ready network monitoring system. "
        "Monitor URL availability, latency, and uptime in real time."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS – tighten origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(targets.router)


# ── Root redirect ─────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }

if __name__ == "__main__":
    import uvicorn
    # This tells Python to start the server when you run 'py -m app.main'
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
