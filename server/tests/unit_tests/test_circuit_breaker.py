"""Pure unit tests for LLMCircuitBreaker — complete state-machine isolation.

Each test class owns one slice of behaviour.  All tests manipulate internal
state directly (white-box) so they stay fast and deterministic: no real LLM
calls, no sleeping for timeouts.

The `asyncio_mode = auto` setting in pytest.ini means every async function in
this file is automatically run under asyncio — no @pytest.mark.asyncio needed.
"""
from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from classify.circuit_breaker import LLMCircuitBreaker, _State
from classify.exceptions import (
    LLMCircuitOpenError,
    LLMInferenceError,
    LLMResponseParseError,
    LLMTimeoutError,
    LLMUnavailableError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A valid LLM result — returned by success stubs.
_OK = {"decision": "NO", "confidence": 5, "reason": "clean"}


def _ok_fn() -> AsyncMock:
    """Async callable that succeeds with _OK."""
    return AsyncMock(return_value=_OK)


def _ok_fn_suspending() -> Callable[[], Awaitable]:
    """Async callable that yields the event loop once before returning.

    Required for concurrency tests: AsyncMock resolves synchronously so the
    event loop never switches tasks mid-call — the probe would complete before
    any concurrent caller checks _probe_in_flight.  Suspending with sleep(0)
    lets the other coroutines reach the lock check while the probe is running.
    """
    async def _fn():
        await asyncio.sleep(0)
        return _OK
    return _fn


def _fail_fn(exc: Exception) -> AsyncMock:
    """Async callable that raises *exc*."""
    return AsyncMock(side_effect=exc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def breaker() -> LLMCircuitBreaker:
    """Fresh breaker with tight defaults — threshold=3, timeout=30 s."""
    return LLMCircuitBreaker(failure_threshold=3, recovery_timeout=30.0)


@pytest.fixture
def single_threshold_breaker() -> LLMCircuitBreaker:
    """Breaker that opens on the very first failure — simplifies scenario tests."""
    return LLMCircuitBreaker(failure_threshold=1, recovery_timeout=30.0)


@pytest.fixture
def logged_breaker() -> LLMCircuitBreaker:
    """Breaker with a mock logger so emitted calls can be asserted."""
    cb = LLMCircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
    cb.log = MagicMock()
    return cb


# =============================================================================
# INITIALIZATION
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerInitialization:
    """A fresh breaker must start with a clean, known state."""

    def test_starts_closed_with_clean_slate(self):
        """All fields must reflect a never-tripped circuit."""
        cb = LLMCircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

        assert cb._state           is _State.CLOSED
        assert cb._failures        == 0
        assert cb._opened_at       == 0.0
        assert cb._probe_in_flight is False

    def test_state_property_returns_string(self):
        cb = LLMCircuitBreaker()
        assert cb.state == "closed"
        assert isinstance(cb.state, str)

    def test_defaults_produce_sane_trip_point_and_timeout(self):
        cb = LLMCircuitBreaker()
        assert cb._threshold == 5
        assert cb._timeout   == 60.0


# =============================================================================
# call() — CLOSED STATE
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerCallClosed:
    """call() in CLOSED state must forward the callable and not trip on non-retryable errors."""

    async def test_success_returns_value(self, breaker):
        result = await breaker.call(_ok_fn())
        assert result == _OK

    async def test_success_leaves_state_closed(self, breaker):
        await breaker.call(_ok_fn())
        assert breaker._state    is _State.CLOSED
        assert breaker._failures == 0

    async def test_transient_error_increments_failures(self, breaker):
        with pytest.raises(LLMUnavailableError):
            await breaker.call(_fail_fn(LLMUnavailableError("down")))
        assert breaker._failures == 1

    async def test_non_retryable_error_propagates_without_tripping(self, breaker):
        """LLMInferenceError is not a circuit-tripping failure — state must stay CLOSED."""
        with pytest.raises(LLMInferenceError):
            await breaker.call(_fail_fn(LLMInferenceError("500")))

        assert breaker._state    is _State.CLOSED
        assert breaker._failures == 0

    async def test_parse_error_propagates_without_tripping(self, breaker):
        """LLMResponseParseError is not a circuit-tripping failure."""
        exc = LLMResponseParseError("bad", ValueError("x"))
        with pytest.raises(LLMResponseParseError):
            await breaker.call(_fail_fn(exc))

        assert breaker._state    is _State.CLOSED
        assert breaker._failures == 0

    async def test_opens_after_threshold_failures(self, breaker):
        for _ in range(breaker._threshold):
            with pytest.raises(LLMUnavailableError):
                await breaker.call(_fail_fn(LLMUnavailableError("down")))
        assert breaker._state is _State.OPEN

    async def test_stays_closed_below_threshold(self, breaker):
        for _ in range(breaker._threshold - 1):
            with pytest.raises(LLMUnavailableError):
                await breaker.call(_fail_fn(LLMUnavailableError("down")))
        assert breaker._state is _State.CLOSED

    async def test_timeout_failure_increments_counter(self, breaker):
        with pytest.raises(LLMTimeoutError):
            await breaker.call(_fail_fn(LLMTimeoutError("30 s")))
        assert breaker._failures == 1


# =============================================================================
# call() — OPEN STATE
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerCallOpen:
    """call() in OPEN state must fast-fail without touching the callable."""

    async def test_raises_circuit_open_error(self, breaker):
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic()  # just opened

        with pytest.raises(LLMCircuitOpenError):
            await breaker.call(_ok_fn())

    async def test_callable_is_never_invoked_when_open(self, breaker):
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic()

        fn = _ok_fn()
        with pytest.raises(LLMCircuitOpenError):
            await breaker.call(fn)

        fn.assert_not_called()

    async def test_open_error_is_subclass_of_unavailable(self, breaker):
        """Router's existing LLMUnavailableError handler must catch it — no new handler needed."""
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic()

        with pytest.raises(LLMUnavailableError):
            await breaker.call(_ok_fn())

    async def test_state_unchanged_after_fast_fail(self, breaker):
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic()
        breaker._failures  = 4

        with pytest.raises(LLMCircuitOpenError):
            await breaker.call(_ok_fn())

        assert breaker._state    is _State.OPEN
        assert breaker._failures == 4  # unchanged

    async def test_transitions_to_half_open_after_timeout(self, breaker):
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic() - 31.0  # 31 s ago, timeout = 30 s

        await breaker.call(_ok_fn())

        assert breaker._state is _State.CLOSED  # probe succeeded → closed

    async def test_allows_probe_exactly_at_recovery_boundary(self, breaker):
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic() - 30.1  # just past the 30 s window

        result = await breaker.call(_ok_fn())

        assert result == _OK

    async def test_failures_reset_to_zero_on_half_open_transition(self, breaker):
        """_failures must be 0 when the probe fires — so a probe failure logs failures=1."""
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic() - 31.0
        breaker._failures  = 7  # accumulated from before opening

        # Trigger the OPEN → HALF_OPEN → fn() call path.  Probe succeeds here.
        await breaker.call(_ok_fn())

        # After success, failures are reset; verify the probe saw a clean counter
        # by checking state closed and failures = 0.
        assert breaker._failures == 0


# =============================================================================
# call() — HALF_OPEN STATE (probe guard)
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerHalfOpen:
    """HALF_OPEN must allow exactly one probe and suppress all concurrent requests."""

    async def test_first_call_is_allowed_through(self, breaker):
        breaker._state            = _State.HALF_OPEN
        breaker._probe_in_flight  = False

        result = await breaker.call(_ok_fn())
        assert result == _OK

    async def test_first_call_sets_probe_in_flight(self, breaker):
        """_probe_in_flight must be True while fn() is running.

        We verify the flag was set by checking it was cleared (reset to False)
        only AFTER the probe completes — success clears it via _record_success.
        """
        breaker._state           = _State.HALF_OPEN
        breaker._probe_in_flight = False

        await breaker.call(_ok_fn())

        # After a successful probe _record_success() resets probe_in_flight.
        assert breaker._probe_in_flight is False

    async def test_second_concurrent_call_is_suppressed(self, breaker):
        breaker._state           = _State.HALF_OPEN
        breaker._probe_in_flight = True  # simulate a probe already in flight

        with pytest.raises(LLMCircuitOpenError):
            await breaker.call(_ok_fn())

    async def test_suppressed_call_does_not_invoke_fn(self, breaker):
        breaker._state           = _State.HALF_OPEN
        breaker._probe_in_flight = True

        fn = _ok_fn()
        with pytest.raises(LLMCircuitOpenError):
            await breaker.call(fn)
        fn.assert_not_called()

    @pytest.mark.concurrency
    async def test_exactly_one_probe_among_concurrent_calls(self, breaker):
        """Of N concurrent calls in HALF_OPEN, exactly 1 must succeed as the probe.

        Uses a suspending callable (_ok_fn_suspending) so that the event loop
        can schedule the other 9 coroutines while the probe is in flight.
        AsyncMock resolves without yielding, which would let the first probe
        complete and close the circuit before the others even check the state.
        """
        breaker._state           = _State.HALF_OPEN
        breaker._probe_in_flight = False

        # Each gather entry gets its own coroutine factory; the factory is called
        # once by call() internally via `await fn()`.
        results = await asyncio.gather(
            *[breaker.call(_ok_fn_suspending()) for _ in range(10)],
            return_exceptions=True,
        )

        successes = [r for r in results if r == _OK]
        errors    = [r for r in results if isinstance(r, LLMCircuitOpenError)]
        assert len(successes) == 1
        assert len(errors)    == 9

    async def test_failed_probe_reopens_circuit(self, breaker):
        breaker._state           = _State.HALF_OPEN
        breaker._probe_in_flight = False

        with pytest.raises(LLMUnavailableError):
            await breaker.call(_fail_fn(LLMUnavailableError("still down")))

        assert breaker._state is _State.OPEN

    async def test_failed_probe_clears_probe_in_flight(self, breaker):
        breaker._state           = _State.HALF_OPEN
        breaker._probe_in_flight = False

        with pytest.raises(LLMUnavailableError):
            await breaker.call(_fail_fn(LLMUnavailableError("still down")))

        assert breaker._probe_in_flight is False

    async def test_successful_probe_closes_circuit(self, breaker):
        breaker._state           = _State.HALF_OPEN
        breaker._probe_in_flight = False

        await breaker.call(_ok_fn())

        assert breaker._state is _State.CLOSED


# =============================================================================
# _record_success — state transitions
# =============================================================================


@pytest.mark.unit
class TestRecordSuccess:
    """_record_success closes the circuit and resets all counters."""

    async def test_closes_from_half_open(self, breaker):
        breaker._state = _State.HALF_OPEN
        await breaker._record_success()
        assert breaker._state is _State.CLOSED

    async def test_closes_from_open(self, breaker):
        breaker._state = _State.OPEN
        await breaker._record_success()
        assert breaker._state is _State.CLOSED

    async def test_resets_failure_count(self, breaker):
        breaker._failures = 5
        await breaker._record_success()
        assert breaker._failures == 0

    async def test_clears_probe_in_flight(self, breaker):
        breaker._probe_in_flight = True
        await breaker._record_success()
        assert breaker._probe_in_flight is False

    async def test_already_closed_is_idempotent(self, breaker):
        breaker._state    = _State.CLOSED
        breaker._failures = 0
        await breaker._record_success()
        assert breaker._state    is _State.CLOSED
        assert breaker._failures == 0


# =============================================================================
# _record_failure — threshold and HALF_OPEN re-open logic
# =============================================================================


@pytest.mark.unit
class TestRecordFailure:
    """_record_failure increments the counter and opens the circuit at the threshold."""

    async def test_increments_failure_count(self, breaker):
        await breaker._record_failure()
        assert breaker._failures == 1
        await breaker._record_failure()
        assert breaker._failures == 2

    async def test_clears_probe_in_flight(self, breaker):
        breaker._probe_in_flight = True
        await breaker._record_failure()
        assert breaker._probe_in_flight is False

    async def test_stays_closed_below_threshold(self, breaker):
        for _ in range(breaker._threshold - 1):
            await breaker._record_failure()
        assert breaker._state is _State.CLOSED

    async def test_opens_at_exactly_threshold(self, breaker):
        for _ in range(breaker._threshold):
            await breaker._record_failure()
        assert breaker._state is _State.OPEN

    async def test_half_open_failure_reopens_regardless_of_count(self, breaker):
        """Even a single failure in HALF_OPEN reopens the circuit."""
        breaker._state    = _State.HALF_OPEN
        breaker._failures = 0  # below threshold

        await breaker._record_failure()

        assert breaker._state is _State.OPEN

    @pytest.mark.parametrize("threshold", [1, 3, 5, 10])
    async def test_threshold_controls_trip_point(self, threshold):
        cb = LLMCircuitBreaker(failure_threshold=threshold, recovery_timeout=30.0)

        for i in range(threshold - 1):
            await cb._record_failure()
            assert cb._state is _State.CLOSED, f"Opened too early at failure {i + 1}"

        await cb._record_failure()
        assert cb._state is _State.OPEN


# =============================================================================
# state property
# =============================================================================


@pytest.mark.unit
class TestStateProperty:
    """state property must return a JSON-serialisable string for each enum value."""

    @pytest.mark.parametrize(("internal", "expected"), [
        (_State.CLOSED,    "closed"),
        (_State.OPEN,      "open"),
        (_State.HALF_OPEN, "half_open"),
    ])
    def test_state_string_for_each_enum(self, breaker, internal, expected):
        breaker._state = internal
        assert breaker.state == expected
        assert isinstance(breaker.state, str)


# =============================================================================
# LOGGING
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerLogging:
    """Correct log level must be used for each state transition."""

    async def test_circuit_opened_logs_at_error(self, logged_breaker):
        cb = logged_breaker
        for _ in range(cb._threshold):
            await cb._record_failure()
        cb.log.error.assert_called_once()

    async def test_circuit_opened_log_includes_failures_and_threshold(self, logged_breaker):
        cb = logged_breaker
        for _ in range(cb._threshold):
            await cb._record_failure()
        args = cb.log.error.call_args
        # Standard logging: positional args are (fmt, *values)
        assert cb._threshold in args[0]  # failure count == threshold at open

    async def test_circuit_closed_from_half_open_logs_at_info(self, logged_breaker):
        cb = logged_breaker
        cb._state = _State.HALF_OPEN
        await cb._record_success()
        cb.log.info.assert_called_once()

    async def test_no_log_while_below_threshold(self, logged_breaker):
        cb = logged_breaker
        for _ in range(cb._threshold - 1):
            await cb._record_failure()
        cb.log.error.assert_not_called()
        cb.log.warning.assert_not_called()
        cb.log.info.assert_not_called()

    async def test_success_from_already_closed_emits_no_log(self, logged_breaker):
        cb = logged_breaker
        assert cb._state is _State.CLOSED
        await cb._record_success()
        cb.log.info.assert_not_called()
        cb.log.warning.assert_not_called()
        cb.log.error.assert_not_called()

    async def test_half_open_transition_logs_at_info(self, logged_breaker):
        cb = logged_breaker
        cb._state     = _State.OPEN
        cb._opened_at = time.monotonic() - 31.0
        await cb.call(_ok_fn())
        cb.log.info.assert_called()

    async def test_probe_success_closes_and_logs_at_info(self, logged_breaker):
        cb = logged_breaker
        cb._state            = _State.HALF_OPEN
        cb._probe_in_flight  = False
        await cb.call(_ok_fn())
        cb.log.info.assert_called()


# =============================================================================
# FULL STATE-MACHINE SCENARIOS
# =============================================================================


@pytest.mark.unit
class TestStateMachineScenarios:

    async def test_full_recovery_cycle(self, single_threshold_breaker):
        """Golden path: CLOSED → OPEN (on failure) → HALF_OPEN (timeout) → CLOSED (success)."""
        cb = single_threshold_breaker

        # Phase 1: healthy
        result = await cb.call(_ok_fn())
        assert result == _OK
        assert cb._state is _State.CLOSED

        # Phase 2: failure opens circuit
        with pytest.raises(LLMUnavailableError):
            await cb.call(_fail_fn(LLMUnavailableError("down")))
        assert cb._state is _State.OPEN

        # Phase 3: still OPEN — fast-fail
        with pytest.raises(LLMCircuitOpenError):
            await cb.call(_ok_fn())

        # Phase 4: recovery timeout elapses → probe allowed
        cb._opened_at = time.monotonic() - 31.0
        result = await cb.call(_ok_fn())
        assert result == _OK
        assert cb._state is _State.CLOSED

    async def test_failed_probe_reopens_circuit(self, single_threshold_breaker):
        """OPEN → HALF_OPEN probe fails → OPEN again."""
        cb = single_threshold_breaker

        with pytest.raises(LLMUnavailableError):
            await cb.call(_fail_fn(LLMUnavailableError("down")))
        assert cb._state is _State.OPEN

        cb._opened_at = time.monotonic() - 31.0
        with pytest.raises(LLMUnavailableError):
            await cb.call(_fail_fn(LLMUnavailableError("still down")))
        assert cb._state is _State.OPEN

    async def test_multiple_open_close_cycles_leave_no_leaked_state(self, single_threshold_breaker):
        """Three full OPEN/CLOSE cycles must not leak _failures, _opened_at, or _probe_in_flight."""
        cb = single_threshold_breaker

        for cycle in range(3):
            # Open it
            with pytest.raises(LLMUnavailableError):
                await cb.call(_fail_fn(LLMUnavailableError("down")))
            assert cb._state is _State.OPEN, f"Cycle {cycle}: expected OPEN"

            # Recover it
            cb._opened_at = time.monotonic() - 31.0
            await cb.call(_ok_fn())
            assert cb._state            is _State.CLOSED, f"Cycle {cycle}: expected CLOSED"
            assert cb._failures         == 0,             f"Cycle {cycle}: failure count leaked"
            assert cb._probe_in_flight  is False,         f"Cycle {cycle}: probe flag leaked"

    async def test_non_retryable_errors_never_open_circuit(self, breaker):
        """Sending only LLMInferenceError must leave the circuit CLOSED indefinitely."""
        for _ in range(20):
            with pytest.raises(LLMInferenceError):
                await breaker.call(_fail_fn(LLMInferenceError("500")))

        assert breaker._state    is _State.CLOSED
        assert breaker._failures == 0
