from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    UNHEALTHY = "unhealthy"


class MongoDBCheck(BaseModel):
    status:          HealthStatus
    latency_ms:      float | None = None
    circuit_breaker: Literal["closed", "open", "half_open"] = "closed"
    error:           str   | None = None


class OllamaCheck(BaseModel):
    status:          HealthStatus
    model:           str
    latency_ms:      float | None = None
    circuit_breaker: str
    error:           str   | None = None


class WordsFilterCheck(BaseModel):
    status:             HealthStatus
    entries:            int
    refresh_task_alive: bool


class HealthChecks(BaseModel):
    mongodb:      MongoDBCheck
    ollama:       OllamaCheck
    words_filter: WordsFilterCheck


class ReadinessResponse(BaseModel):
    status:         HealthStatus
    version:        str
    uptime_seconds: float = Field(..., description="Seconds since the server started")
    checks:         HealthChecks


class LivenessResponse(BaseModel):
    status: str = "alive"
