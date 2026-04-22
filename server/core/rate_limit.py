"""Application-wide rate limiter singleton.

A single Limiter is created here and imported by every router that needs it,
the same pattern as core/database.py for the MongoDB pool.  This keeps the
storage backend in one place: swap MemoryStorage for RedisStorage here and
every decorated endpoint picks it up automatically.

Storage backend:
  MemoryStorage  — default, suitable for a single-process deployment.
  RedisStorage   — drop-in replacement for multi-process / multi-instance.
                   To migrate: pip install limits[redis] and replace the
                   storage_uri below with "redis://host:6379".

Key function:
  get_remote_address returns request.client.host (the direct TCP peer).
  In production behind a reverse proxy, add FastAPI's ProxyHeadersMiddleware
  so Uvicorn populates request.client.host from X-Forwarded-For before the
  limiter reads it — never trust that header raw in the key function.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    # MemoryStorage is the default; named explicitly so a future Redis
    # migration is a one-line change here rather than a library-level hunt.
    storage_uri="memory://",
)
