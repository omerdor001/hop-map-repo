"""Unit tests for the per-child classify rate limiter (classify.service).

Tests directly invoke the async helpers and assert on observable behaviour.
No external services, no real MongoDB, no LLM — fully isolated.

asyncio_mode=auto (pytest.ini) means every async test runs under asyncio
without needing @pytest.mark.asyncio.

Coverage:
  TestClassifyRateLimit  — check_rate_limit allow/reject semantics
  TestSweepOnce          — _sweep_once eviction logic
  TestSweepTaskLifecycle — start_sweep_task / stop_sweep_task / is_sweep_task_alive
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

import classify.service as svc
from config import config_manager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def reset_state():
    """Full isolation: cancel any running sweep task and clear store before/after each test."""
    await svc.stop_sweep_task()
    svc._sweep_task = None
    svc._classify_call_times.clear()
    yield
    await svc.stop_sweep_task()
    svc._sweep_task = None
    svc._classify_call_times.clear()


@pytest.fixture()
async def running_sweep_task():
    """Provide a live sweep task for lifecycle tests; guaranteed to be cancelled on teardown."""
    await svc.start_sweep_task()
    yield
    await svc.stop_sweep_task()
    svc._sweep_task = None


# ---------------------------------------------------------------------------
# check_rate_limit — allow / reject semantics
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestClassifyRateLimit:

    async def test_first_call_is_allowed(self):
        assert await svc.check_rate_limit("child-1") is True

    async def test_calls_within_limit_are_all_allowed(self):
        for _ in range(config_manager.classify_max_rpm):
            assert await svc.check_rate_limit("child-2") is True

    async def test_call_exceeding_limit_is_rejected(self):
        for _ in range(config_manager.classify_max_rpm):
            await svc.check_rate_limit("child-3")
        assert await svc.check_rate_limit("child-3") is False

    async def test_expired_timestamps_do_not_count_toward_limit(self):
        old_ts = time.monotonic() - 61.0
        svc._classify_call_times["child-4"] = [old_ts] * config_manager.classify_max_rpm
        assert await svc.check_rate_limit("child-4") is True

    async def test_two_children_are_isolated(self):
        for _ in range(config_manager.classify_max_rpm):
            await svc.check_rate_limit("child-a")
        assert await svc.check_rate_limit("child-a") is False
        assert await svc.check_rate_limit("child-b") is True

    async def test_limit_boundary_is_exact(self):
        for i in range(config_manager.classify_max_rpm):
            result = await svc.check_rate_limit("child-5")
            assert result is True, f"call {i + 1} should be allowed"
        assert await svc.check_rate_limit("child-5") is False


# ---------------------------------------------------------------------------
# _sweep_once — eviction logic
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSweepOnce:
    """_sweep_once is tested via patched time so assertions are deterministic
    and independent of wall-clock speed."""

    async def test_removes_stale_entry(self):
        svc._classify_call_times["stale"] = [time.monotonic() - 61.0]
        await svc._sweep_once()
        assert "stale" not in svc._classify_call_times

    async def test_preserves_active_entry(self):
        svc._classify_call_times["active"] = [time.monotonic()]
        await svc._sweep_once()
        assert "active" in svc._classify_call_times

    async def test_evicts_stale_and_preserves_active(self):
        svc._classify_call_times["stale"]  = [time.monotonic() - 61.0]
        svc._classify_call_times["active"] = [time.monotonic()]
        await svc._sweep_once()
        assert "stale"  not in svc._classify_call_times
        assert "active" in     svc._classify_call_times

    async def test_returns_count_of_evicted_entries(self):
        old = time.monotonic() - 61.0
        svc._classify_call_times["stale-1"] = [old]
        svc._classify_call_times["stale-2"] = [old]
        svc._classify_call_times["active"]  = [time.monotonic()]
        assert await svc._sweep_once() == 2

    async def test_returns_zero_when_nothing_to_evict(self):
        svc._classify_call_times["active"] = [time.monotonic()]
        assert await svc._sweep_once() == 0

    async def test_returns_zero_on_empty_store(self):
        assert await svc._sweep_once() == 0

    async def test_evicts_entry_with_empty_timestamp_list(self):
        svc._classify_call_times["broken"] = []
        await svc._sweep_once()
        assert "broken" not in svc._classify_call_times

    async def test_staleness_uses_most_recent_timestamp(self):
        # Many old timestamps but the last one is fresh — entry must survive.
        old = time.monotonic() - 61.0
        svc._classify_call_times["mixed"] = [old, old, time.monotonic()]
        await svc._sweep_once()
        assert "mixed" in svc._classify_call_times

    async def test_evicts_all_stale_entries(self):
        old = time.monotonic() - 61.0
        for i in range(5):
            svc._classify_call_times[f"stale-{i}"] = [old]
        assert await svc._sweep_once() == 5
        assert len(svc._classify_call_times) == 0

    async def test_store_is_consistent_after_partial_eviction(self):
        old = time.monotonic() - 61.0
        svc._classify_call_times["stale"]   = [old]
        svc._classify_call_times["active1"] = [time.monotonic()]
        svc._classify_call_times["active2"] = [time.monotonic()]
        await svc._sweep_once()
        assert set(svc._classify_call_times) == {"active1", "active2"}

    async def test_sweep_loop_calls_sweep_once_after_interval(self):
        """_sweep_loop invokes _sweep_once exactly once when the sleep completes."""
        with patch("classify.service.asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
             patch("classify.service._sweep_once", new_callable=AsyncMock) as mock_sweep:
            # First sleep returns immediately (sweep fires), second raises CancelledError
            # which _sweep_loop catches and returns from — so no exception propagates.
            mock_sleep.side_effect = [None, asyncio.CancelledError()]
            await svc._sweep_loop()
        mock_sweep.assert_called_once()

    async def test_sweep_loop_sleeps_for_sweep_interval(self):
        """_sweep_loop passes _SWEEP_INTERVAL to asyncio.sleep."""
        with patch("classify.service.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # CancelledError on first sleep — loop catches it and returns cleanly.
            mock_sleep.side_effect = asyncio.CancelledError()
            await svc._sweep_loop()
        mock_sleep.assert_called_once_with(svc._SWEEP_INTERVAL)


# ---------------------------------------------------------------------------
# start_sweep_task / stop_sweep_task / is_sweep_task_alive — lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSweepTaskLifecycle:
    """Lifecycle API mirrors the words-service refresh-task contract exactly."""

    async def test_is_alive_false_before_start(self):
        # reset_state fixture ensures _sweep_task is None before this runs.
        assert svc.is_sweep_task_alive() is False

    async def test_is_alive_true_after_start(self, running_sweep_task):
        assert svc.is_sweep_task_alive() is True

    async def test_is_alive_false_after_stop(self):
        await svc.start_sweep_task()
        await svc.stop_sweep_task()
        assert svc.is_sweep_task_alive() is False

    async def test_stop_is_safe_when_never_started(self):
        # _sweep_task is None (guaranteed by reset_state) — must not raise.
        assert svc._sweep_task is None
        await svc.stop_sweep_task()

    async def test_stop_cancels_the_task(self):
        await svc.start_sweep_task()
        task = svc._sweep_task
        await svc.stop_sweep_task()
        assert task.cancelled()

    async def test_task_does_not_sweep_immediately_on_start(self, running_sweep_task):
        """The sweep loop sleeps first — stale entries must survive the initial yield."""
        svc._classify_call_times["stale"] = [time.monotonic() - 61.0]
        await asyncio.sleep(0)  # yield to let the event loop schedule the new task
        assert "stale" in svc._classify_call_times
