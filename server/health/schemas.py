from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class HealthStatus(str, Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    UNHEALTHY = "unhealthy"


class MongoDBCheck(BaseModel):
    status:          HealthStatus
    latency_ms:      float | None = None
    circuit_breaker: Literal["closed", "open", "half_open"] = "closed"
    error:           str   | None = None


class LLMCheck(BaseModel):
    status:          HealthStatus
    provider:        str
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
    llm:          LLMCheck
    words_filter: WordsFilterCheck

    @computed_field
    @property
    def ollama(self) -> LLMCheck:
        """Deprecated alias for ``llm``. Will be removed in a future release.

        The field was renamed from ``ollama`` to ``llm`` to support multiple
        providers.  Both keys are present in the response during the transition
        window so existing monitoring dashboards and alerting rules keep working.
        """
        return self.llm


class ReadinessResponse(BaseModel):
    status:         HealthStatus
    version:        str
    uptime_seconds: float = Field(..., description="Seconds since the server started")
    checks:         HealthChecks


class LivenessResponse(BaseModel):
    status: str = "alive"
