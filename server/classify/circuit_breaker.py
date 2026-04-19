"""Three-state async circuit breaker for LLM availability failures.

State machine:
  CLOSED    — normal operation; consecutive failures increment a counter.
  OPEN      — fast-fail; no calls forwarded until recovery_timeout elapses.
  HALF_OPEN — one probe attempt; success closes the circuit, failure re-opens.

Only LLMUnavailableError and LLMTimeoutError are treated as circuit-tripping
failures — they indicate the LLM daemon is unreachable or unresponsive.
LLMInferenceError and LLMResponseParseError are request-level issues and do
not affect circuit state.
"""
from __future__ import annotations

import asyncio
import enum
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from classify.exceptions import LLMCircuitOpenError, LLMTimeoutError, LLMUnavailableError

T = TypeVar("T")

_TRIPPING_ERRORS = (LLMUnavailableError, LLMTimeoutError)


class _State(enum.Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


class LLMCircuitBreaker:
    """Async circuit breaker wrapping any awaitable callable.

    Args:
        failure_threshold: Consecutive transient failures before opening.
        recovery_timeout:  Seconds the circuit stays OPEN before a probe is allowed.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        self._threshold        = failure_threshold
        self._timeout          = recovery_timeout
        self._state            = _State.CLOSED
        self._failures         = 0
        self._opened_at        = 0.0
        self._probe_in_flight  = False  # only one probe allowed while HALF_OPEN
        self._lock             = asyncio.Lock()
        self.log               = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state.value

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Execute *fn* under circuit-breaker protection.

        Raises:
            LLMCircuitOpenError: If the circuit is OPEN and the recovery
                timeout has not elapsed yet — caller should not retry.
        """
        async with self._lock:
            if self._state is _State.OPEN:
                elapsed   = time.monotonic() - self._opened_at
                remaining = self._timeout - elapsed
                if remaining > 0:
                    raise LLMCircuitOpenError(
                        f"Circuit OPEN — LLM calls suppressed ({remaining:.0f}s remaining)"
                    )
                # Recovery window elapsed — allow one probe.
                self._state    = _State.HALF_OPEN
                self._failures = 0  # reset so probe-failure count starts at 1
                self.log.info("Circuit breaker → HALF_OPEN (probe after %.0fs open)", elapsed)

            if self._state is _State.HALF_OPEN:
                if self._probe_in_flight:
                    # A probe is already running — suppress concurrent requests
                    # rather than sending a thundering-herd of probes at once.
                    raise LLMCircuitOpenError(
                        "Circuit HALF_OPEN — probe already in flight"
                    )
                self._probe_in_flight = True

        try:
            result = await fn()
        except _TRIPPING_ERRORS:
            await self._record_failure()
            raise
        else:
            await self._record_success()
            return result

    # ------------------------------------------------------------------
    # Internal state transitions
    # ------------------------------------------------------------------

    async def _record_success(self) -> None:
        async with self._lock:
            if self._state is _State.HALF_OPEN:
                self.log.info("Circuit breaker → CLOSED (probe succeeded)")
            self._state           = _State.CLOSED
            self._failures        = 0
            self._probe_in_flight = False

    async def _record_failure(self) -> None:
        async with self._lock:
            self._failures       += 1
            self._probe_in_flight = False
            if self._state is _State.HALF_OPEN or self._failures >= self._threshold:
                self._state     = _State.OPEN
                self._opened_at = time.monotonic()
                self.log.error(
                    "Circuit breaker → OPEN  failures=%d  threshold=%d",
                    self._failures,
                    self._threshold,
                )
