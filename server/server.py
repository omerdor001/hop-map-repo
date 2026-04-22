"""
HopMap Server — entry point.

Responsibilities are split across feature packages:
  auth/        — parent registration, login, JWT, session management
  children/    — child registration and management
  classify/    — LLM content classification + hop event ingestion
  events/      — SSE streaming + event history
  words/       — blocked-words filter management
  notifications/ — parent notification inbox
  platforms/   — platform→process mappings served to agents
  core/        — shared database pool, validators
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from config import APP_VERSION, config_manager
from core.db_circuit_breaker import DatabaseCircuitOpenError
from core.rate_limit import limiter
from core.startup import validate_secrets
from llm import get_provider

# Feature routers
from auth.router import router as auth_router
from children.router import router as children_router
from classify.router import router as classify_router
from events.router import router as events_router
from health.router import record_startup, router as health_router
from me.router import router as me_router
from notifications.router import router as notifications_router
from platforms.router import router as platforms_router
from words.router import router as words_router

# Services that need lifecycle management
from classify import service as classify_service
from events import service as event_service
from words import service as words_service
from platforms import service as platforms_service

# Index initializers from each repository
from auth.repository import initialize_indexes as auth_indexes
from children.repository import initialize_indexes as children_indexes
from events.repository import initialize_indexes as events_indexes
from notifications.repository import initialize_indexes as notifications_indexes
from words.repository import initialize_indexes as words_indexes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("hopmap-server")


async def _on_db_circuit_open(request: Request, exc: DatabaseCircuitOpenError) -> JSONResponse:
    """Return 503 when the MongoDB circuit breaker is OPEN.

    Includes Retry-After so well-behaved clients back off instead of hammering
    the server.  The value is conservative — the circuit timeout is configurable
    and may be longer, but clients should not assume the exact remaining window.
    """
    # Cap Retry-After at 60 s regardless of the configured recovery timeout.
    # Clients should not be told to wait the full circuit timeout (which may
    # be several minutes); a shorter hint keeps them from giving up entirely
    # while the circuit self-heals.
    retry_after = min(int(config_manager.db.circuit_breaker_recovery_timeout_seconds), 60)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable. Please try again later."},
        headers={"Retry-After": str(retry_after)},
    )


async def _on_rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return 429 in the same {detail: ...} shape FastAPI uses for HTTPException.

    Also sets Retry-After per RFC 6585 §4 so clients can back off correctly.
    """
    response = JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )
    response.headers["Retry-After"] = str(exc.retry_after) if hasattr(exc, "retry_after") else "60"
    view_rate_limit = getattr(request.state, "view_rate_limit", None)
    if view_rate_limit is not None:
        response = request.app.state.limiter._inject_headers(response, view_rate_limit)
    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_secrets(config_manager)
    log.info("HopMap server starting.")

    # Initialize LLM provider
    classify_service.set_llm(get_provider(
        name=config_manager.llm.provider,
        model=config_manager.llm.model,
    ))

    # Ensure MongoDB indexes exist
    auth_indexes()
    children_indexes()
    events_indexes()
    notifications_indexes()
    words_indexes()

    # Seed + load blocked words, start background refresh
    words_service.seed_if_empty(config_manager.data.words_db_path)
    words_service.load_blocked_words()
    await words_service.start_refresh_task()

    # Start background sweep that evicts stale per-child rate-limit entries
    await classify_service.start_sweep_task()

    # Load platform→process mappings
    platforms_service.load_platforms_db()

    record_startup()
    yield

    log.info("HopMap server shutting down.")
    await classify_service.stop_sweep_task()
    await words_service.stop_refresh_task()
    await event_service.shutdown_all()


app = FastAPI(title="HopMap API", version=APP_VERSION, lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(DatabaseCircuitOpenError, _on_db_circuit_open)
app.add_exception_handler(RateLimitExceeded, _on_rate_limit_exceeded)

# SlowAPIMiddleware must be added before CORSMiddleware so that rate-limited
# requests are rejected before CORS headers are processed.
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config_manager.network.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(children_router)
app.include_router(classify_router)
app.include_router(events_router)
app.include_router(me_router)
app.include_router(notifications_router)
app.include_router(platforms_router)
app.include_router(words_router)


if __name__ == "__main__":
    log.info(
        "Starting HopMap server on %s:%d",
        config_manager.network.host,
        config_manager.network.port,
    )
    try:
        uvicorn.run(
            "server:app",
            host=config_manager.network.host,
            port=config_manager.network.port,
            reload=False,
            timeout_graceful_shutdown=2,
        )
    except KeyboardInterrupt:
        log.info("Server shutting down — goodbye.")
