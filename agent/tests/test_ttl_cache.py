"""Unit tests for _TTLCache — bounded, time-expiring membership set."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

import agent as _agent


_TTLCache = _agent._TTLCache


class TestTTLCacheBasic:

    def test_new_key_returns_false(self):
        cache = _TTLCache(ttl_seconds=60, max_size=100)
        assert cache.seen("key1") is False

    def test_second_call_same_key_returns_true(self):
        cache = _TTLCache(ttl_seconds=60, max_size=100)
        cache.seen("key1")           # first call — records the key
        assert cache.seen("key1") is True

    def test_different_keys_are_independent(self):
        cache = _TTLCache(ttl_seconds=60, max_size=100)
        cache.seen("a")
        assert cache.seen("b") is False

    def test_seen_returns_bool_not_truthy(self):
        cache = _TTLCache(ttl_seconds=60, max_size=100)
        first = cache.seen("x")
        assert first is False
        second = cache.seen("x")
        assert second is True


class TestTTLCacheExpiry:

    def test_entry_expires_after_ttl(self):
        """After TTL seconds the key is treated as new again."""
        cache = _TTLCache(ttl_seconds=5, max_size=100)
        # Record key at t=0.
        with patch("time.monotonic", return_value=0.0):
            cache.seen("url1")

        # Simulate t=6 (past TTL).
        with patch("time.monotonic", return_value=6.0):
            result = cache.seen("url1")

        assert result is False  # expired — treated as a new entry

    def test_entry_not_expired_within_ttl(self):
        cache = _TTLCache(ttl_seconds=10, max_size=100)
        with patch("time.monotonic", return_value=0.0):
            cache.seen("url2")

        with patch("time.monotonic", return_value=9.0):  # still within window
            result = cache.seen("url2")

        assert result is True


class TestTTLCacheBoundedSize:

    def test_exceeding_max_size_evicts_oldest(self):
        cache = _TTLCache(ttl_seconds=300, max_size=3)
        cache.seen("a")
        cache.seen("b")
        cache.seen("c")
        # Adding a 4th entry should evict "a" (oldest).
        cache.seen("d")
        # "a" is evicted — should be treated as new.
        assert cache.seen("a") is False

    def test_size_never_exceeds_max(self):
        cache = _TTLCache(ttl_seconds=300, max_size=5)
        for i in range(20):
            cache.seen(f"url-{i}")
        assert len(cache._store) <= 5


class TestTTLCacheThreadSafety:

    def test_concurrent_access_does_not_raise(self):
        """Smoke test: concurrent threads must not corrupt state."""
        import threading
        cache = _TTLCache(ttl_seconds=60, max_size=1000)
        errors = []

        def worker(tid):
            try:
                for i in range(50):
                    cache.seen(f"t{tid}-url{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
