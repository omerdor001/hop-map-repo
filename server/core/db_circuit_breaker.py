"""Synchronous circuit breaker for MongoDB operations.

State machine (identical semantics to the async LLM breaker):
  CLOSED    — normal operation; consecutive tripping failures increment a counter.
  OPEN      — fast-fail; guard() raises immediately until recovery_timeout elapses.
  HALF_OPEN — one probe request is allowed through; success closes the circuit,
              failure re-opens it.

Tripping errors are connectivity failures only — errors that indicate the server
is unreachable or unresponsive.  Application-layer errors (DuplicateKeyError,
OperationFailure, InvalidId) are NOT tripping errors and do not affect circuit
state.

Threading model:
  All state transitions are guarded by threading.Lock so the breaker is safe to
  use from any thread — including the worker threads FastAPI uses when calling
  synchronous functions via asyncio.to_thread().

_ProtectedCollection:
  A transparent proxy around a PyMongo Collection.  Every attribute access that
  returns a callable is wrapped so that:
    * guard() is called before each operation (fast-fails if circuit is OPEN).
    * record_success() / record_failure() are called after each operation.
  Repositories require no changes — they call the proxy exactly as they would
  call a real Collection.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from typing import Any

from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure

log = logging.getLogger(__name__)

# ConnectionFailure is the base class for every PyMongo connectivity error:
# AutoReconnect, ServerSelectionTimeoutError, NetworkTimeout, WaitQueueTimeoutError.
# A single isinstance check covers all of them, so no subclasses are listed.
_TRIPPING_ERRORS = (ConnectionFailure,)


class DatabaseCircuitOpenError(RuntimeError):
    """Raised by guard() when the circuit is OPEN or a probe is already in flight.

    Caught by the global exception handler in server.py and returned as HTTP 503
    so callers receive a structured error rather than an unhandled 500.
    """


class _State(enum.Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


class DatabaseCircuitBreaker:
    """Synchronous three-state circuit breaker for MongoDB connectivity.

    Args:
        failure_threshold: Consecutive tripping failures before the circuit opens.
        recovery_timeout:  Seconds the circuit stays OPEN before a probe is allowed.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self._threshold       = failure_threshold
        self._timeout         = recovery_timeout
        self._state           = _State.CLOSED
        self._failures        = 0
        self._opened_at       = 0.0
        self._probe_in_flight = False
        self._lock            = threading.Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state.value

    def guard(self) -> None:
        """Check circuit state before allowing a database operation.

        Raises:
            DatabaseCircuitOpenError: If the circuit is OPEN and the recovery
                timeout has not elapsed, or if a HALF_OPEN probe is already
                in flight (thundering-herd guard).
        """
        with self._lock:
            if self._state is _State.OPEN:
                elapsed   = time.monotonic() - self._opened_at
                remaining = self._timeout - elapsed
                if remaining > 0:
                    raise DatabaseCircuitOpenError(
                        f"Circuit OPEN — DB calls suppressed ({remaining:.0f}s remaining)"
                    )
                # Recovery window elapsed — allow one probe.
                self._state    = _State.HALF_OPEN
                self._failures = 0
                log.info("DB circuit breaker → HALF_OPEN (probe after %.0fs open)", elapsed)

            if self._state is _State.HALF_OPEN:
                if self._probe_in_flight:
                    raise DatabaseCircuitOpenError(
                        "Circuit HALF_OPEN — probe already in flight"
                    )
                self._probe_in_flight = True

    def record_success(self) -> None:
        """Record a successful database operation.

        Transitions HALF_OPEN → CLOSED and resets all failure counters.
        Called by _ProtectedCollection after every non-exceptional method call.
        """
        with self._lock:
            if self._state is _State.HALF_OPEN:
                log.info("DB circuit breaker → CLOSED (probe succeeded)")
            self._state           = _State.CLOSED
            self._failures        = 0
            self._probe_in_flight = False

    def record_failure(self) -> None:
        """Record a tripping failure (connectivity error).

        Increments the failure counter and transitions CLOSED → OPEN once the
        threshold is reached, or immediately re-opens from HALF_OPEN.
        Called by _ProtectedCollection when a _TRIPPING_ERRORS exception is caught.
        """
        with self._lock:
            self._failures       += 1
            self._probe_in_flight = False
            if self._state is _State.HALF_OPEN or self._failures >= self._threshold:
                self._state     = _State.OPEN
                self._opened_at = time.monotonic()
                log.error(
                    "DB circuit breaker → OPEN  failures=%d  threshold=%d",
                    self._failures,
                    self._threshold,
                )


class _ProtectedCollection:
    """Transparent proxy around a PyMongo Collection that enforces circuit-breaker rules.

    Every callable attribute (find_one, insert_one, update_one, …) is wrapped:
      1. guard() is called first — raises DatabaseCircuitOpenError if OPEN.
      2. record_success() is called on a clean return.
      3. record_failure() is called and the exception is re-raised on _TRIPPING_ERRORS.
      4. Non-tripping exceptions (DuplicateKeyError, OperationFailure, …) pass
         through untouched — they do not affect circuit state.

    Non-callable attributes (e.g. ``Collection.name``) are forwarded directly
    without going through the breaker.

    Repositories use this exactly like a real ``Collection`` — no call-site
    changes are required.  Instances are created by ``DatabasePool.get_collection()``
    and should not be constructed directly.
    """

    __slots__ = ("_col", "_breaker")

    def __init__(self, collection: Collection, breaker: DatabaseCircuitBreaker) -> None:
        object.__setattr__(self, "_col",     collection)
        object.__setattr__(self, "_breaker", breaker)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(object.__getattribute__(self, "_col"), name)
        if not callable(attr):
            return attr

        breaker = object.__getattribute__(self, "_breaker")

        def _protected(*args: Any, **kwargs: Any) -> Any:
            breaker.guard()
            try:
                result = attr(*args, **kwargs)
            except _TRIPPING_ERRORS:
                breaker.record_failure()
                raise
            else:
                breaker.record_success()
                return result

        return _protected
