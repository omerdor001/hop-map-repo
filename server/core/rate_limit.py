"""Application-wide rate limiter singleton.

A single Limiter is created here and imported by every router that needs it,
the same pattern as core/database.py for the MongoDB pool.  This keeps the
storage backend in one place: set HOPMAP_SERVER__REDIS__URL and every
decorated endpoint picks up Redis storage automatically.

Storage backend:
  MemoryStorage  — default when redis.url is empty; suitable for single-process.
  RedisStorage   — used automatically when redis.url is set; safe for multi-worker.
                   Requires: pip install 'limits[redis]'

Key function:
  get_remote_address returns request.client.host (the direct TCP peer).
  In production behind a reverse proxy, add FastAPI's ProxyHeadersMiddleware
  so Uvicorn populates request.client.host from X-Forwarded-For before the
  limiter reads it — never trust that header raw in the key function.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from config import config_manager

# Use Redis when configured; fall back to in-process MemoryStorage for
# single-worker deployments.  The startup validator (core/startup.py) ensures
# the server refuses to start with workers > 1 and no Redis URL configured.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=config_manager.redis.url or "memory://",
)
