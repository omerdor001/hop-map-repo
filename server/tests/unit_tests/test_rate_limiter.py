"""Unit tests for the per-child classify rate limiter (classify.service).

Tests directly invoke the async rate-limit helper and assert on allow/reject
behaviour.  No external services required.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

import classify.service as classify_service
from config import config_manager


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear rate-limiter state before each test for isolation."""
    classify_service._classify_call_times.clear()
    yield
    classify_service._classify_call_times.clear()


class TestClassifyRateLimit:

    @pytest.mark.asyncio
    async def test_first_call_is_allowed(self):
        assert await classify_service.check_rate_limit("child-1") is True

    @pytest.mark.asyncio
    async def test_calls_within_limit_all_allowed(self):
        for _ in range(30):
            assert await classify_service.check_rate_limit("child-2") is True

    @pytest.mark.asyncio
    async def test_31st_call_is_rejected(self):
        for _ in range(30):
            await classify_service.check_rate_limit("child-3")
        assert await classify_service.check_rate_limit("child-3") is False

    @pytest.mark.asyncio
    async def test_expired_timestamps_are_evicted(self):
        old_ts = time.monotonic() - 61.0
        classify_service._classify_call_times["child-4"] = [old_ts] * 30
        assert await classify_service.check_rate_limit("child-4") is True

    @pytest.mark.asyncio
    async def test_two_children_are_isolated(self):
        for _ in range(30):
            await classify_service.check_rate_limit("child-a")
        assert await classify_service.check_rate_limit("child-a") is False
        assert await classify_service.check_rate_limit("child-b") is True

    @pytest.mark.asyncio
    async def test_limit_is_exactly_max_rpm(self):
        for i in range(config_manager.classify_max_rpm):
            res = await classify_service.check_rate_limit("child-5")
            assert res is True, f"Expected True on call {i + 1}"
        assert await classify_service.check_rate_limit("child-5") is False
