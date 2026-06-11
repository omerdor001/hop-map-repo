"""Server startup validators.

All checks in this module run before any service is initialised.  Violations
are either fatal (production / staging) or surfaced as warnings (development)
so that local dev remains ergonomic while production deployments are protected.

Adding a new check:
  1. Write a function that returns a list[str] of violation messages (empty = OK).
  2. Call it inside validate_secrets() and extend `violations`.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import ServerConfig

log = logging.getLogger(__name__)

# The placeholder written into the default config.  Any deployment that never
# touched the secret will still carry this exact string.
_DEFAULT_JWT_SECRET = "change-me-in-production"

# RFC 7518 §3.2: HMAC-SHA256 keys SHOULD be at least 256 bits (32 bytes).
# 32 printable ASCII characters satisfy this for typical secrets; we use 32 as
# the hard floor and recommend 64+ in the message.
_JWT_SECRET_MIN_LEN = 32

# The env-var operators must set when scaling beyond a single process.
_REDIS_URL_ENV_VAR = "HOPMAP_SERVER__REDIS__URL"

# LLM providers that require HOPMAP_SERVER__LLM__API_KEY to be non-empty.
# When adding a new cloud provider to server/llm/__init__.py, add its name here too.
_CLOUD_PROVIDERS: frozenset[str] = frozenset({"nvidia"})


def _check_jwt_secret(jwt_secret: str) -> list[str]:
    violations: list[str] = []

    if jwt_secret == _DEFAULT_JWT_SECRET:
        violations.append(
            "JWT secret is the well-known default value 'change-me-in-production'. "
            "Any attacker can forge tokens with this secret. "
            "Set HOPMAP_SERVER__AUTH__JWT_SECRET to a random string of ≥32 characters "
            "(generate one with: python -c \"import secrets; print(secrets.token_hex(64))\")."
        )
    elif len(jwt_secret) < _JWT_SECRET_MIN_LEN:
        # Separate branch: not the default, but still too short.
        violations.append(
            f"JWT secret is only {len(jwt_secret)} character(s) long. "
            f"RFC 7518 §3.2 requires HS256 keys to be ≥{_JWT_SECRET_MIN_LEN} characters. "
            "Set HOPMAP_SERVER__AUTH__JWT_SECRET to a longer secret."
        )

    return violations


def _check_multi_worker(cfg: "ServerConfig") -> list[str]:
    """Return a violation if workers > 1 without a Redis URL.

    Why this is required:
      SSE event queues (events/service.py _sse_queues) and the per-child
      classify rate-limit counters (classify/service.py _classify_call_times)
      are module-level dicts that live inside a single process.  With multiple
      worker processes each worker holds its own independent copy — a hop event
      received by worker A is broadcast only to SSE clients connected to worker
      A; worker B's clients receive nothing.  Rate-limit counters diverge the
      same way, effectively multiplying the allowed request budget by the
      worker count.

      Redis solves this: slowapi can use RedisStorage for auth rate-limits
      (one-line change via config), and SSE pub/sub can be migrated to a Redis
      channel when the need arises.  Until then, single-worker is the only
      safe deployment mode.
    """
    if cfg.network.workers <= 1:
        return []
    if cfg.redis.url:
        return []
    return [
        f"workers={cfg.network.workers} but {_REDIS_URL_ENV_VAR} is not set. "
        "Multi-worker deployments require shared state for SSE event queues and "
        "per-child classify rate-limit counters — in-process dicts diverge "
        "silently across worker processes, causing missed SSE events and "
        "under-enforced rate limits. "
        f"Set {_REDIS_URL_ENV_VAR}=redis://host:6379 and install "
        "'limits[redis]', or set workers=1."
    ]


def _check_llm_config(cfg: "ServerConfig") -> list[str]:
    """Return a violation if a cloud LLM provider is selected without an API key."""
    if cfg.llm.provider in _CLOUD_PROVIDERS and not cfg.llm.api_key.get_secret_value().strip():
        return [
            f"LLM_PROVIDER is set to '{cfg.llm.provider}' but HOPMAP_SERVER__LLM__API_KEY "
            "is empty or blank. Cloud providers require an API key. "
            "Set HOPMAP_SERVER__LLM__API_KEY in .env, or switch to provider='ollama' "
            "for local inference."
        ]
    return []


def validate_secrets(cfg: "ServerConfig") -> None:
    """Validate all secrets and deployment constraints required for secure operation.

    In *development* every violation is logged at WARNING level and the server
    continues to start.  In *staging* and *production* every violation is
    logged at CRITICAL level and the process exits with code 1 — the server
    must never start with a misconfigured secret in a live environment.
    """
    violations = _check_jwt_secret(cfg.auth.jwt_secret)
    violations.extend(_check_multi_worker(cfg))
    violations.extend(_check_llm_config(cfg))

    if not violations:
        return

    is_production = cfg.environment in ("staging", "production")
    log_fn = log.critical if is_production else log.warning

    log_fn(
        "Startup validation failed (%d violation(s)) [environment=%s]",
        len(violations),
        cfg.environment,
    )
    for i, msg in enumerate(violations, start=1):
        log_fn("  [%d/%d] %s", i, len(violations), msg)

    if is_production:
        log.critical(
            "Refusing to start in '%s' environment with insecure secrets. "
            "Fix the violation(s) above, then restart the server.",
            cfg.environment,
        )
        sys.exit(1)
    else:
        log.warning(
            "Server starting with insecure secrets (environment=%s). "
            "This is only acceptable for local development.",
            cfg.environment,
        )
