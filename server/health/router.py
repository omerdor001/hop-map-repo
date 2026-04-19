from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import APP_VERSION
from health.checks import check_mongodb, check_ollama, check_words_filter
from health.schemas import HealthChecks, HealthStatus, LivenessResponse, ReadinessResponse

# Overwritten by record_startup() in the lifespan; module-load time is the fallback.
_startup_time: float = time.monotonic()

router = APIRouter(prefix="/health", tags=["health"])

_HTTP_STATUS: dict[HealthStatus, int] = {
    HealthStatus.HEALTHY:   200,
    HealthStatus.DEGRADED:  200,  # service is partially functional; load-balancer keeps routing
    HealthStatus.UNHEALTHY: 503,
}


def record_startup() -> None:
    """Called from the lifespan context after all startup tasks complete,
    so uptime_seconds reflects real readiness rather than import time.
    """
    global _startup_time
    _startup_time = time.monotonic()


def _aggregate(
    mongodb: HealthStatus,
    ollama:  HealthStatus,
    words:   HealthStatus,
) -> HealthStatus:
    if mongodb is HealthStatus.UNHEALTHY:
        return HealthStatus.UNHEALTHY
    if any(s is not HealthStatus.HEALTHY for s in (mongodb, ollama, words)):
        return HealthStatus.DEGRADED
    return HealthStatus.HEALTHY


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
    description=(
        "Always returns HTTP 200 while the process is alive. "
        "Kubernetes uses this to decide whether to restart the pod."
    ),
)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description=(
        "Checks MongoDB, Ollama, and the words filter concurrently. "
        "Returns 200 when the service can handle traffic. "
        "Returns 503 when MongoDB (the critical dependency) is unreachable. "
        "A 200 with status=degraded means the service is up but operating with reduced capability."
    ),
)
async def readiness() -> JSONResponse:
    mongo, ollama_check, words = await asyncio.gather(
        check_mongodb(),
        check_ollama(),
        check_words_filter(),
    )
    overall = _aggregate(mongo.status, ollama_check.status, words.status)
    body = ReadinessResponse(
        status=overall,
        version=APP_VERSION,
        uptime_seconds=round(time.monotonic() - _startup_time, 2),
        checks=HealthChecks(
            mongodb=mongo,
            ollama=ollama_check,
            words_filter=words,
        ),
    )
    return JSONResponse(content=body.model_dump(), status_code=_HTTP_STATUS[overall])
