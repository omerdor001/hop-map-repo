"""Health check probes for each infrastructure dependency.

Each function is async, bounded by _CHECK_TIMEOUT, and never raises —
callers always receive a typed result they can inspect and aggregate.

LLM check dispatch
------------------
  ollama  — pings the local daemon and verifies the configured model is pulled.
  nvidia  — reports circuit-breaker state only; no remote ping (avoids burning
            API credits and decouples the health endpoint from NVIDIA's uptime).
"""
from __future__ import annotations

import asyncio
import time

from classify.service import get_circuit_breaker_state
from config import config_manager
from core.database import pool as db_pool
from health.schemas import HealthStatus, LLMCheck, MongoDBCheck, WordsFilterCheck
from words import service as words_service

_DB_CIRCUIT_OPEN = "open"

_CHECK_TIMEOUT = 5.0  # seconds; applied per probe via asyncio.wait_for


def _ping_db() -> bool:
    return db_pool.ping()


async def _ping_db_async() -> bool:
    return await asyncio.to_thread(_ping_db)


async def check_mongodb() -> MongoDBCheck:
    circuit_state = db_pool.circuit_breaker.state

    # When the circuit is OPEN the server is known to be unreachable — skip
    # the ping entirely to avoid blocking the health endpoint for up to
    # _CHECK_TIMEOUT seconds on a dead connection.
    if circuit_state == _DB_CIRCUIT_OPEN:
        return MongoDBCheck(
            status=HealthStatus.UNHEALTHY,
            circuit_breaker=circuit_state,
            error="circuit breaker OPEN — MongoDB calls suppressed",
        )

    start = time.perf_counter()
    try:
        ok = await asyncio.wait_for(
            _ping_db_async(),
            timeout=_CHECK_TIMEOUT,
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        if ok:
            return MongoDBCheck(
                status=HealthStatus.HEALTHY,
                latency_ms=latency_ms,
                circuit_breaker=circuit_state,
            )
        return MongoDBCheck(
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency_ms,
            circuit_breaker=circuit_state,
            error="ping returned False — connection may be stale",
        )
    except asyncio.TimeoutError:
        return MongoDBCheck(
            status=HealthStatus.UNHEALTHY,
            circuit_breaker=circuit_state,
            error=f"ping timed out after {_CHECK_TIMEOUT:.0f}s",
        )
    except Exception as exc:
        return MongoDBCheck(
            status=HealthStatus.UNHEALTHY,
            circuit_breaker=circuit_state,
            error=str(exc),
        )


def _list_ollama_model_names() -> list[str]:
    """Return names of locally available Ollama models (blocking; run via to_thread)."""
    import ollama  # lazy — only imported when provider == "ollama"
    return [m.model for m in ollama.list().models]


async def _list_ollama_models_async() -> list[str]:
    return await asyncio.to_thread(_list_ollama_model_names)


async def _check_ollama(model: str, circuit_state: str) -> LLMCheck:
    """Ping the local Ollama daemon and verify the configured model is pulled."""
    start = time.perf_counter()
    try:
        available  = await asyncio.wait_for(
            _list_ollama_models_async(),
            timeout=_CHECK_TIMEOUT,
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        if model in available:
            return LLMCheck(
                status=HealthStatus.HEALTHY,
                provider="ollama",
                model=model,
                latency_ms=latency_ms,
                circuit_breaker=circuit_state,
            )
        return LLMCheck(
            status=HealthStatus.DEGRADED,
            provider="ollama",
            model=model,
            latency_ms=latency_ms,
            circuit_breaker=circuit_state,
            error=f"model '{model}' not in local library — run: ollama pull {model}",
        )
    except asyncio.TimeoutError:
        return LLMCheck(
            status=HealthStatus.UNHEALTHY,
            provider="ollama",
            model=model,
            circuit_breaker=circuit_state,
            error=f"ollama unreachable: list() timed out after {_CHECK_TIMEOUT:.0f}s",
        )
    except Exception as exc:
        return LLMCheck(
            status=HealthStatus.UNHEALTHY,
            provider="ollama",
            model=model,
            circuit_breaker=circuit_state,
            error=str(exc),
        )


def _circuit_to_status(circuit_state: str) -> HealthStatus:
    if circuit_state == "closed":
        return HealthStatus.HEALTHY
    if circuit_state == "half_open":
        return HealthStatus.DEGRADED
    return HealthStatus.UNHEALTHY  # open


def _check_nvidia(model: str, circuit_state: str) -> LLMCheck:
    """Report circuit-breaker state for the NVIDIA NIM provider.

    No remote ping is performed — health checks must not burn API credits
    or introduce a hard dependency on NVIDIA's infrastructure uptime.
    The circuit breaker is the sole health signal: it reflects real
    inference failures observed in production traffic.
    """
    return LLMCheck(
        status=_circuit_to_status(circuit_state),
        provider="nvidia",
        model=model,
        circuit_breaker=circuit_state,
    )


async def check_llm() -> LLMCheck:
    """Dispatch to the appropriate provider health probe."""
    provider      = config_manager.llm.provider
    model         = config_manager.llm.model
    circuit_state = get_circuit_breaker_state()

    if provider == "ollama":
        return await _check_ollama(model, circuit_state)
    if provider == "nvidia":
        return _check_nvidia(model, circuit_state)

    # Unknown provider — surface the misconfiguration without crashing the probe.
    return LLMCheck(
        status=HealthStatus.UNHEALTHY,
        provider=provider,
        model=model,
        circuit_breaker=circuit_state,
        error=f"Unknown LLM provider {provider!r} — check LLM_PROVIDER in config.",
    )


async def check_words_filter() -> WordsFilterCheck:
    entries    = words_service.get_entry_count()
    task_alive = words_service.is_refresh_task_alive()
    status     = HealthStatus.HEALTHY if entries > 0 else HealthStatus.DEGRADED
    return WordsFilterCheck(
        status=status,
        entries=entries,
        refresh_task_alive=task_alive,
    )
