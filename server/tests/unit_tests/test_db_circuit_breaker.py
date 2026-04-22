"""Pure unit tests for DatabaseCircuitBreaker and _ProtectedCollection.

Each test class owns one slice of behaviour.  Tests manipulate internal state
directly (white-box) so they remain fast and fully deterministic — no real
MongoDB connections, no sleeping for timeouts.

The `asyncio_mode = auto` setting in pytest.ini means no @pytest.mark.asyncio
decoration is needed.  Sync tests in this file run normally.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pymongo.errors import (
    AutoReconnect,
    ConnectionFailure,
    DuplicateKeyError,
    OperationFailure,
    ServerSelectionTimeoutError,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.db_circuit_breaker import (
    DatabaseCircuitBreaker,
    DatabaseCircuitOpenError,
    _ProtectedCollection,
    _State,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def breaker() -> DatabaseCircuitBreaker:
    """Fresh breaker: threshold=3, timeout=30 s."""
    return DatabaseCircuitBreaker(failure_threshold=3, recovery_timeout=30.0)


@pytest.fixture
def single_threshold_breaker() -> DatabaseCircuitBreaker:
    """Breaker that opens on the very first failure — simplifies scenario tests."""
    return DatabaseCircuitBreaker(failure_threshold=1, recovery_timeout=30.0)


@pytest.fixture
def mock_collection() -> MagicMock:
    """Minimal PyMongo Collection stub."""
    col = MagicMock()
    col.name = "test_collection"
    return col


# ---------------------------------------------------------------------------
# INITIALIZATION
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDatabaseCircuitBreakerInit:
    """A fresh breaker must start with a clean, known state."""

    def test_starts_in_clean_closed_state(self):
        cb = DatabaseCircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        assert cb._state           is _State.CLOSED
        assert cb._failures        == 0
        assert cb._opened_at       == 0.0
        assert cb._probe_in_flight is False

    def test_accepts_custom_threshold_and_timeout(self):
        cb = DatabaseCircuitBreaker(failure_threshold=2, recovery_timeout=60.0)
        assert cb._threshold == 2
        assert cb._timeout   == 60.0

    def test_state_property_returns_string(self):
        cb = DatabaseCircuitBreaker()
        assert cb.state == "closed"
        assert isinstance(cb.state, str)


# ---------------------------------------------------------------------------
# guard() — CLOSED STATE
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGuardClosed:
    """guard() must be a no-op when the circuit is CLOSED."""

    def test_does_not_raise(self, breaker):
        breaker.guard()  # must not raise

    def test_leaves_all_state_unchanged(self, breaker):
        breaker.guard()
        assert breaker._state           is _State.CLOSED
        assert breaker._failures        == 0
        assert breaker._probe_in_flight is False


# ---------------------------------------------------------------------------
# guard() — OPEN STATE
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGuardOpen:
    """guard() must fast-fail immediately when the circuit is OPEN."""

    def test_raises_before_timeout_elapses(self, breaker):
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic()
        with pytest.raises(DatabaseCircuitOpenError):
            breaker.guard()

    def test_error_message_includes_remaining_seconds(self, breaker):
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic()
        with pytest.raises(DatabaseCircuitOpenError, match=r"\d+s remaining"):
            breaker.guard()

    def test_state_and_failure_count_unchanged_after_fast_fail(self, breaker):
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic()
        breaker._failures  = 4
        with pytest.raises(DatabaseCircuitOpenError):
            breaker.guard()
        assert breaker._state    is _State.OPEN
        assert breaker._failures == 4

    def test_transitions_to_half_open_after_recovery_timeout(self, breaker):
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic() - 31.0  # 31 s ago; timeout = 30 s
        breaker.guard()
        assert breaker._state           is _State.HALF_OPEN
        assert breaker._probe_in_flight is True

    def test_still_allows_probe_exactly_at_recovery_boundary(self, breaker):
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic() - 30.1  # just past 30 s
        breaker.guard()  # must not raise
        assert breaker._state is _State.HALF_OPEN

    def test_failures_reset_to_zero_on_half_open_transition(self, breaker):
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic() - 31.0
        breaker._failures  = 7
        breaker.guard()
        assert breaker._failures == 0


# ---------------------------------------------------------------------------
# guard() — HALF_OPEN STATE
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGuardHalfOpen:
    """guard() must allow exactly one probe in HALF_OPEN and block all others."""

    def test_first_call_sets_probe_in_flight(self, breaker):
        breaker._state           = _State.HALF_OPEN
        breaker._probe_in_flight = False
        breaker.guard()
        assert breaker._probe_in_flight is True

    def test_second_call_raises_when_probe_already_in_flight(self, breaker):
        breaker._state           = _State.HALF_OPEN
        breaker._probe_in_flight = True
        with pytest.raises(DatabaseCircuitOpenError, match="probe already in flight"):
            breaker.guard()

    def test_blocked_call_does_not_change_state(self, breaker):
        breaker._state           = _State.HALF_OPEN
        breaker._probe_in_flight = True
        with pytest.raises(DatabaseCircuitOpenError):
            breaker.guard()
        assert breaker._state           is _State.HALF_OPEN
        assert breaker._probe_in_flight is True


# ---------------------------------------------------------------------------
# record_success()
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRecordSuccess:
    """record_success() must close the circuit and reset all counters."""

    def test_closes_from_half_open(self, breaker):
        breaker._state = _State.HALF_OPEN
        breaker.record_success()
        assert breaker._state is _State.CLOSED

    def test_resets_failure_count_and_probe_flag(self, breaker):
        breaker._state           = _State.HALF_OPEN
        breaker._failures        = 3
        breaker._probe_in_flight = True
        breaker.record_success()
        assert breaker._failures        == 0
        assert breaker._probe_in_flight is False

    def test_idempotent_when_already_closed(self, breaker):
        breaker._state    = _State.CLOSED
        breaker._failures = 0
        breaker.record_success()
        assert breaker._state    is _State.CLOSED
        assert breaker._failures == 0


# ---------------------------------------------------------------------------
# record_failure()
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRecordFailure:
    """record_failure() must increment the counter and open at the threshold."""

    def test_increments_failure_count(self, breaker):
        breaker.record_failure()
        assert breaker._failures == 1
        breaker.record_failure()
        assert breaker._failures == 2

    def test_clears_probe_in_flight(self, breaker):
        breaker._probe_in_flight = True
        breaker.record_failure()
        assert breaker._probe_in_flight is False

    def test_stays_closed_below_threshold(self, breaker):
        for _ in range(breaker._threshold - 1):
            breaker.record_failure()
        assert breaker._state is _State.CLOSED

    def test_opens_exactly_at_threshold(self, breaker):
        for _ in range(breaker._threshold):
            breaker.record_failure()
        assert breaker._state is _State.OPEN

    def test_records_opened_at_timestamp(self, breaker):
        before = time.monotonic()
        for _ in range(breaker._threshold):
            breaker.record_failure()
        after = time.monotonic()
        assert before <= breaker._opened_at <= after

    def test_half_open_failure_reopens_regardless_of_count(self, breaker):
        """Even a single failure in HALF_OPEN must re-open — threshold does not apply."""
        breaker._state    = _State.HALF_OPEN
        breaker._failures = 0  # below threshold
        breaker.record_failure()
        assert breaker._state is _State.OPEN

    @pytest.mark.parametrize("threshold", [1, 2, 5, 10])
    def test_threshold_controls_trip_point(self, threshold):
        cb = DatabaseCircuitBreaker(failure_threshold=threshold, recovery_timeout=30.0)
        for i in range(threshold - 1):
            cb.record_failure()
            assert cb._state is _State.CLOSED, f"Opened too early at failure {i + 1}"
        cb.record_failure()
        assert cb._state is _State.OPEN


# ---------------------------------------------------------------------------
# state property
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStateProperty:
    """state property must return a JSON-serialisable string for every enum value."""

    @pytest.mark.parametrize(("internal", "expected"), [
        (_State.CLOSED,    "closed"),
        (_State.OPEN,      "open"),
        (_State.HALF_OPEN, "half_open"),
    ])
    def test_state_string_for_each_enum(self, breaker, internal, expected):
        breaker._state = internal
        assert breaker.state == expected
        assert isinstance(breaker.state, str)


# ---------------------------------------------------------------------------
# _ProtectedCollection — tripping error classification
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTrippingErrorClassification:
    """Only connectivity errors must trip the circuit; application errors must not."""

    @pytest.mark.parametrize("exc_class", [
        ConnectionFailure,
        ServerSelectionTimeoutError,  # subclass of ConnectionFailure
        AutoReconnect,                # subclass of ConnectionFailure
    ])
    def test_connectivity_error_trips_circuit(self, mock_collection, breaker, exc_class):
        mock_collection.find_one.side_effect = exc_class("server down")
        proxy = _ProtectedCollection(mock_collection, breaker)
        with pytest.raises(exc_class):
            proxy.find_one({})
        assert breaker._failures == 1

    @pytest.mark.parametrize("exc_class", [
        DuplicateKeyError,
        OperationFailure,
        ValueError,
        RuntimeError,
    ])
    def test_non_connectivity_error_does_not_trip_circuit(self, mock_collection, breaker, exc_class):
        mock_collection.find_one.side_effect = exc_class("app error")
        proxy = _ProtectedCollection(mock_collection, breaker)
        with pytest.raises(exc_class):
            proxy.find_one({})
        assert breaker._failures == 0
        assert breaker._state    is _State.CLOSED


# ---------------------------------------------------------------------------
# _ProtectedCollection — proxy behaviour
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProtectedCollection:
    """The proxy must transparently forward calls and wire the circuit breaker."""

    def test_forwards_return_value(self, mock_collection, breaker):
        mock_collection.find_one.return_value = {"_id": "abc", "name": "test"}
        proxy = _ProtectedCollection(mock_collection, breaker)
        assert proxy.find_one({"_id": "abc"}) == {"_id": "abc", "name": "test"}

    def test_forwards_args_and_kwargs(self, mock_collection, breaker):
        proxy = _ProtectedCollection(mock_collection, breaker)
        proxy.find_one({"x": 1}, projection={"y": 0})
        mock_collection.find_one.assert_called_once_with({"x": 1}, projection={"y": 0})

    def test_non_callable_attribute_bypasses_breaker(self, mock_collection, breaker):
        """Collection.name is a non-callable — must be returned directly, no guard() call."""
        proxy = _ProtectedCollection(mock_collection, breaker)
        assert proxy.name == "test_collection"

    def test_raises_and_does_not_call_underlying_when_circuit_open(self, mock_collection, breaker):
        breaker._state     = _State.OPEN
        breaker._opened_at = time.monotonic()
        proxy = _ProtectedCollection(mock_collection, breaker)
        with pytest.raises(DatabaseCircuitOpenError):
            proxy.find_one({})
        mock_collection.find_one.assert_not_called()

    def test_records_success_after_clean_call(self, mock_collection, breaker):
        breaker._failures = 2  # below threshold — success must reset this
        mock_collection.find_one.return_value = None
        proxy = _ProtectedCollection(mock_collection, breaker)
        proxy.find_one({})
        assert breaker._failures == 0
        assert breaker._state    is _State.CLOSED

    def test_opens_circuit_after_threshold_connectivity_failures(self, mock_collection, breaker):
        mock_collection.find_one.side_effect = ConnectionFailure("timeout")
        proxy = _ProtectedCollection(mock_collection, breaker)
        for _ in range(breaker._threshold):
            with pytest.raises(ConnectionFailure):
                proxy.find_one({})
        assert breaker._state is _State.OPEN

    def test_probe_success_closes_circuit_end_to_end(self, mock_collection, single_threshold_breaker):
        """End-to-end: circuit opens via proxy failure, recovers via proxy success."""
        cb = single_threshold_breaker

        # Open the circuit through the proxy.
        mock_collection.find_one.side_effect = ConnectionFailure("down")
        proxy = _ProtectedCollection(mock_collection, cb)
        with pytest.raises(ConnectionFailure):
            proxy.find_one({})
        assert cb._state is _State.OPEN

        # Simulate recovery window elapsed.
        cb._opened_at = time.monotonic() - 31.0

        # Probe through the proxy — one successful call must close the circuit.
        mock_collection.find_one.side_effect = None
        mock_collection.find_one.return_value = {"ok": True}
        result = proxy.find_one({})
        assert result == {"ok": True}
        assert cb._state    is _State.CLOSED
        assert cb._failures == 0


# ---------------------------------------------------------------------------
# FULL STATE-MACHINE SCENARIOS
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStateMachineScenarios:

    def test_full_recovery_cycle(self, single_threshold_breaker):
        """Golden path: CLOSED → OPEN → HALF_OPEN → CLOSED."""
        cb = single_threshold_breaker

        cb.guard()
        cb.record_success()
        assert cb._state is _State.CLOSED

        cb.record_failure()
        assert cb._state is _State.OPEN

        with pytest.raises(DatabaseCircuitOpenError):
            cb.guard()

        cb._opened_at = time.monotonic() - 31.0
        cb.guard()
        assert cb._state           is _State.HALF_OPEN
        assert cb._probe_in_flight is True

        cb.record_success()
        assert cb._state           is _State.CLOSED
        assert cb._failures        == 0
        assert cb._probe_in_flight is False

    def test_failed_probe_reopens_circuit(self, single_threshold_breaker):
        """OPEN → HALF_OPEN → probe failure → OPEN again."""
        cb = single_threshold_breaker
        cb.record_failure()
        cb._opened_at = time.monotonic() - 31.0
        cb.guard()
        assert cb._state is _State.HALF_OPEN

        cb.record_failure()
        assert cb._state is _State.OPEN

    def test_multiple_open_close_cycles_leave_no_leaked_state(self, single_threshold_breaker):
        """Three full cycles must leave zero leaked state each time."""
        cb = single_threshold_breaker
        for cycle in range(3):
            cb.record_failure()
            assert cb._state is _State.OPEN, f"cycle {cycle}"

            cb._opened_at = time.monotonic() - 31.0
            cb.guard()
            cb.record_success()
            assert cb._state           is _State.CLOSED, f"cycle {cycle}"
            assert cb._failures        == 0,             f"cycle {cycle}"
            assert cb._probe_in_flight is False,         f"cycle {cycle}"

    def test_success_below_threshold_resets_failure_counter(self, breaker):
        """Failures that haven't yet tripped the circuit must be cleared by a success."""
        breaker.record_failure()
        breaker.record_failure()
        assert breaker._failures == 2
        assert breaker._state    is _State.CLOSED

        breaker.record_success()
        assert breaker._failures == 0


# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLogging:
    """Correct log level and message for each state transition."""

    def test_opening_circuit_logs_at_error_with_counts(self, monkeypatch):
        import core.db_circuit_breaker as mod
        mock_log = MagicMock()
        monkeypatch.setattr(mod, "log", mock_log)

        cb = DatabaseCircuitBreaker(failure_threshold=2, recovery_timeout=30.0)
        cb.record_failure()
        cb.record_failure()  # threshold reached — circuit opens

        mock_log.error.assert_called_once()
        fmt, failures, threshold = mock_log.error.call_args[0]
        assert failures  == 2
        assert threshold == 2

    def test_half_open_transition_logs_at_info(self, monkeypatch):
        import core.db_circuit_breaker as mod
        mock_log = MagicMock()
        monkeypatch.setattr(mod, "log", mock_log)

        cb            = DatabaseCircuitBreaker(failure_threshold=1, recovery_timeout=30.0)
        cb._state     = _State.OPEN
        cb._opened_at = time.monotonic() - 31.0
        cb.guard()

        mock_log.info.assert_called_once()
        assert "HALF_OPEN" in mock_log.info.call_args[0][0]

    def test_closing_from_half_open_logs_at_info(self, monkeypatch):
        import core.db_circuit_breaker as mod
        mock_log = MagicMock()
        monkeypatch.setattr(mod, "log", mock_log)

        cb        = DatabaseCircuitBreaker()
        cb._state = _State.HALF_OPEN
        cb.record_success()

        mock_log.info.assert_called_once()
        assert "CLOSED" in mock_log.info.call_args[0][0]

    def test_no_log_emitted_while_below_threshold(self, monkeypatch):
        import core.db_circuit_breaker as mod
        mock_log = MagicMock()
        monkeypatch.setattr(mod, "log", mock_log)

        cb = DatabaseCircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        for _ in range(4):
            cb.record_failure()

        mock_log.error.assert_not_called()
        mock_log.warning.assert_not_called()
        mock_log.info.assert_not_called()

    def test_success_from_closed_emits_no_log(self, monkeypatch):
        import core.db_circuit_breaker as mod
        mock_log = MagicMock()
        monkeypatch.setattr(mod, "log", mock_log)

        cb = DatabaseCircuitBreaker()
        cb.record_success()

        mock_log.info.assert_not_called()
        mock_log.warning.assert_not_called()
        mock_log.error.assert_not_called()


# ---------------------------------------------------------------------------
# THREAD SAFETY
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestThreadSafety:
    """The breaker's threading.Lock must serialise concurrent state mutations."""

    def test_only_one_probe_allowed_among_concurrent_threads(self, breaker):
        """Of N threads all calling guard() in HALF_OPEN, exactly 1 must get the probe."""
        breaker._state           = _State.HALF_OPEN
        breaker._probe_in_flight = False

        n_threads  = 20
        successes  = []
        errors     = []
        barrier    = threading.Barrier(n_threads)

        def _call():
            barrier.wait()  # all threads start simultaneously
            try:
                breaker.guard()
                successes.append(True)
            except DatabaseCircuitOpenError:
                errors.append(True)

        threads = [threading.Thread(target=_call) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(successes) == 1,  f"Expected 1 probe, got {len(successes)}"
        assert len(errors)    == 19, f"Expected 19 blocked, got {len(errors)}"

    def test_failure_counter_is_accurate_under_concurrent_writes(self):
        """record_failure() must be atomic — no lost updates under concurrency."""
        cb       = DatabaseCircuitBreaker(failure_threshold=1000, recovery_timeout=30.0)
        n        = 100
        barrier  = threading.Barrier(n)

        def _fail():
            barrier.wait()
            cb.record_failure()

        threads = [threading.Thread(target=_fail) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert cb._failures == n
