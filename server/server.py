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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import config_manager
from llm import get_provider

# Feature routers
from auth.router import router as auth_router
from children.router import router as children_router
from classify.router import router as classify_router
from events.router import router as events_router
from notifications.router import router as notifications_router
from platforms.router import router as platforms_router
from words.router import router as words_router

# Services that need lifecycle management
from classify import service as classify_service
from core.database import _pool as db_pool
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


@asynccontextmanager
async def lifespan(app: FastAPI):
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

    # Load platform→process mappings
    platforms_service.load_platforms_db()

    yield

    log.info("HopMap server shutting down.")
    await words_service.stop_refresh_task()
    await event_service.shutdown_all()


app = FastAPI(title="HopMap API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config_manager.network.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(children_router)
app.include_router(classify_router)
app.include_router(events_router)
app.include_router(notifications_router)
app.include_router(platforms_router)
app.include_router(words_router)


@app.get("/health")
def health() -> dict:
    db_ok = db_pool.ping()
    return {"status": "ok" if db_ok else "db_unavailable", "db": db_ok}


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
