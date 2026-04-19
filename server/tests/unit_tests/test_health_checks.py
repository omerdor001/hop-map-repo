"""Unit tests for health check probes and aggregation logic.

Tests are fully isolated — no real MongoDB, Ollama, or asyncio tasks.
All external calls are patched at the call-site boundary so each function
is tested in complete isolation.

The `asyncio_mode = auto` setting in pytest.ini means every async test
runs under asyncio automatically — no @pytest.mark.asyncio decorator needed.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from health.checks import _CHECK_TIMEOUT, check_mongodb, check_ollama, check_words_filter
from health.router import _HTTP_STATUS, _aggregate
from health.schemas import (
    HealthStatus,
    MongoDBCheck,
    OllamaCheck,
    WordsFilterCheck,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _healthy_checks() -> tuple[MongoDBCheck, OllamaCheck, WordsFilterCheck]:
    mongo = MongoDBCheck(status=HealthStatus.HEALTHY, latency_ms=1.0)
    oll   = OllamaCheck(status=HealthStatus.HEALTHY, model="qwen2.5:7b",
                        latency_ms=5.0, circuit_breaker="closed")
    words = WordsFilterCheck(status=HealthStatus.HEALTHY, entries=100,
                             refresh_task_alive=True)
    return mongo, oll, words


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_db_ping_ok():
    with patch("health.checks._ping_db_async", new_callable=AsyncMock, return_value=True) as p:
        yield p


@pytest.fixture()
def mock_db_ping_fail():
    with patch("health.checks._ping_db_async", new_callable=AsyncMock, return_value=False) as p:
        yield p


@pytest.fixture()
def mock_circuit_closed():
    with patch("health.checks.get_circuit_breaker_state", return_value="closed") as p:
        yield p


@pytest.fixture()
def mock_circuit_open():
    with patch("health.checks.get_circuit_breaker_state", return_value="open") as p:
        yield p


@pytest.fixture(scope="module")
def health_client():
    """TestClient scoped to the FastAPI app; heavy session setup is handled
    by the global _global_test_setup fixture in tests/conftest.py."""
    from server import app
    from starlette.testclient import TestClient

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


# =============================================================================
# check_mongodb()
# =============================================================================


@pytest.mark.unit
class TestCheckMongoDB:
    """check_mongodb covers healthy, unhealthy, timeout, and exception paths."""

    async def test_returns_healthy_when_ping_succeeds(self, mock_db_ping_ok):
        result = await check_mongodb()
        assert result.status is HealthStatus.HEALTHY
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        assert result.error is None

    async def test_latency_is_positive_float(self, mock_db_ping_ok):
        result = await check_mongodb()
        assert isinstance(result.latency_ms, float)
        assert result.latency_ms >= 0

    async def test_returns_unhealthy_when_ping_returns_false(self, mock_db_ping_fail):
        result = await check_mongodb()
        assert result.status is HealthStatus.UNHEALTHY
        assert result.error is not None
        assert result.latency_ms is not None

    async def test_returns_unhealthy_on_exception(self):
        with patch("health.checks._ping_db_async", new_callable=AsyncMock,
                   side_effect=RuntimeError("connection refused")):
            result = await check_mongodb()
        assert result.status is HealthStatus.UNHEALTHY
        assert "connection refused" in result.error

    async def test_returns_unhealthy_on_timeout(self):
        with patch("health.checks.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await check_mongodb()
        assert result.status is HealthStatus.UNHEALTHY
        assert f"{_CHECK_TIMEOUT:.0f}s" in result.error

    async def test_never_raises(self):
        with patch("health.checks._ping_db_async", new_callable=AsyncMock,
                   side_effect=Exception("unexpected")):
            result = await check_mongodb()
        assert result.status is HealthStatus.UNHEALTHY

    async def test_error_is_none_on_success(self, mock_db_ping_ok):
        result = await check_mongodb()
        assert result.error is None


# =============================================================================
# check_ollama()
# =============================================================================


_LIST_MODELS = "health.checks._list_ollama_models_async"


@pytest.mark.unit
class TestCheckOllama:
    """check_ollama covers model-present, model-missing, unreachable, and timeout paths."""

    async def test_healthy_when_model_present(self, mock_circuit_closed):
        with patch(_LIST_MODELS, new_callable=AsyncMock, return_value=["qwen2.5:7b", "llama3.2:latest"]):
            with patch("health.checks.config_manager") as cfg:
                cfg.llm.model = "qwen2.5:7b"
                result = await check_ollama()
        assert result.status is HealthStatus.HEALTHY
        assert result.error is None
        assert result.latency_ms is not None

    async def test_degraded_when_model_missing(self, mock_circuit_closed):
        with patch(_LIST_MODELS, new_callable=AsyncMock, return_value=["llama3.2:latest"]):
            with patch("health.checks.config_manager") as cfg:
                cfg.llm.model = "qwen2.5:7b"
                result = await check_ollama()
        assert result.status is HealthStatus.DEGRADED
        assert "qwen2.5:7b" in result.error
        assert "ollama pull" in result.error

    async def test_unhealthy_when_daemon_unreachable(self, mock_circuit_closed):
        with patch(_LIST_MODELS, new_callable=AsyncMock, side_effect=ConnectionError("no route")):
            with patch("health.checks.config_manager") as cfg:
                cfg.llm.model = "qwen2.5:7b"
                result = await check_ollama()
        assert result.status is HealthStatus.UNHEALTHY
        assert result.error is not None

    async def test_unhealthy_on_timeout(self, mock_circuit_closed):
        with patch("health.checks.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            with patch("health.checks.config_manager") as cfg:
                cfg.llm.model = "qwen2.5:7b"
                result = await check_ollama()
        assert result.status is HealthStatus.UNHEALTHY
        assert f"{_CHECK_TIMEOUT:.0f}s" in result.error

    async def test_circuit_breaker_state_reflected_in_result(self, mock_circuit_open):
        with patch(_LIST_MODELS, new_callable=AsyncMock, return_value=["qwen2.5:7b"]):
            with patch("health.checks.config_manager") as cfg:
                cfg.llm.model = "qwen2.5:7b"
                result = await check_ollama()
        assert result.circuit_breaker == "open"

    async def test_circuit_breaker_closed_reflected(self, mock_circuit_closed):
        with patch(_LIST_MODELS, new_callable=AsyncMock, return_value=["qwen2.5:7b"]):
            with patch("health.checks.config_manager") as cfg:
                cfg.llm.model = "qwen2.5:7b"
                result = await check_ollama()
        assert result.circuit_breaker == "closed"

    async def test_model_name_in_result(self, mock_circuit_closed):
        with patch(_LIST_MODELS, new_callable=AsyncMock, return_value=["qwen2.5:7b"]):
            with patch("health.checks.config_manager") as cfg:
                cfg.llm.model = "qwen2.5:7b"
                result = await check_ollama()
        assert result.model == "qwen2.5:7b"

    async def test_never_raises(self, mock_circuit_closed):
        with patch(_LIST_MODELS, new_callable=AsyncMock, side_effect=Exception("boom")):
            with patch("health.checks.config_manager") as cfg:
                cfg.llm.model = "qwen2.5:7b"
                result = await check_ollama()
        assert result.status is HealthStatus.UNHEALTHY

    async def test_empty_model_list_yields_degraded(self, mock_circuit_closed):
        with patch(_LIST_MODELS, new_callable=AsyncMock, return_value=[]):
            with patch("health.checks.config_manager") as cfg:
                cfg.llm.model = "qwen2.5:7b"
                result = await check_ollama()
        assert result.status is HealthStatus.DEGRADED


# =============================================================================
# check_words_filter()
# =============================================================================


@pytest.mark.unit
class TestCheckWordsFilter:
    """check_words_filter covers loaded, empty, and task states."""

    async def test_healthy_when_entries_loaded_and_task_alive(self):
        with patch("health.checks.words_service.get_entry_count", return_value=1234):
            with patch("health.checks.words_service.is_refresh_task_alive", return_value=True):
                result = await check_words_filter()
        assert result.status is HealthStatus.HEALTHY
        assert result.entries == 1234
        assert result.refresh_task_alive is True

    async def test_degraded_when_entries_are_zero(self):
        with patch("health.checks.words_service.get_entry_count", return_value=0):
            with patch("health.checks.words_service.is_refresh_task_alive", return_value=True):
                result = await check_words_filter()
        assert result.status is HealthStatus.DEGRADED

    async def test_healthy_even_when_refresh_task_dead(self):
        """Task dying does not degrade the filter if words are loaded — entries are still in memory."""
        with patch("health.checks.words_service.get_entry_count", return_value=500):
            with patch("health.checks.words_service.is_refresh_task_alive", return_value=False):
                result = await check_words_filter()
        assert result.status is HealthStatus.HEALTHY
        assert result.refresh_task_alive is False

    async def test_entries_count_is_forwarded(self):
        with patch("health.checks.words_service.get_entry_count", return_value=42):
            with patch("health.checks.words_service.is_refresh_task_alive", return_value=True):
                result = await check_words_filter()
        assert result.entries == 42

    async def test_task_alive_flag_is_forwarded(self):
        with patch("health.checks.words_service.get_entry_count", return_value=1):
            with patch("health.checks.words_service.is_refresh_task_alive", return_value=False):
                result = await check_words_filter()
        assert result.refresh_task_alive is False


# =============================================================================
# _aggregate()
# =============================================================================


@pytest.mark.unit
class TestAggregate:
    """_aggregate maps per-component statuses to the correct overall status."""

    def test_all_healthy_yields_healthy(self):
        result = _aggregate(HealthStatus.HEALTHY, HealthStatus.HEALTHY, HealthStatus.HEALTHY)
        assert result is HealthStatus.HEALTHY

    def test_mongodb_unhealthy_yields_unhealthy(self):
        result = _aggregate(HealthStatus.UNHEALTHY, HealthStatus.HEALTHY, HealthStatus.HEALTHY)
        assert result is HealthStatus.UNHEALTHY

    def test_mongodb_unhealthy_overrides_degraded_ollama(self):
        result = _aggregate(HealthStatus.UNHEALTHY, HealthStatus.DEGRADED, HealthStatus.HEALTHY)
        assert result is HealthStatus.UNHEALTHY

    def test_ollama_unhealthy_yields_degraded(self):
        result = _aggregate(HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.HEALTHY)
        assert result is HealthStatus.DEGRADED

    def test_ollama_degraded_yields_degraded(self):
        result = _aggregate(HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.HEALTHY)
        assert result is HealthStatus.DEGRADED

    def test_words_degraded_yields_degraded(self):
        result = _aggregate(HealthStatus.HEALTHY, HealthStatus.HEALTHY, HealthStatus.DEGRADED)
        assert result is HealthStatus.DEGRADED

    def test_ollama_and_words_both_degraded_yields_degraded(self):
        result = _aggregate(HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.DEGRADED)
        assert result is HealthStatus.DEGRADED

    @pytest.mark.parametrize("mongo", [HealthStatus.HEALTHY, HealthStatus.DEGRADED])
    def test_mongo_non_unhealthy_cannot_yield_unhealthy(self, mongo):
        result = _aggregate(mongo, HealthStatus.HEALTHY, HealthStatus.HEALTHY)
        assert result is not HealthStatus.UNHEALTHY


# =============================================================================
# HTTP status code mapping
# =============================================================================


@pytest.mark.unit
class TestHTTPStatusMapping:
    """_HTTP_STATUS must map exactly per contract."""

    def test_healthy_maps_to_200(self):
        assert _HTTP_STATUS[HealthStatus.HEALTHY] == 200

    def test_degraded_maps_to_200(self):
        assert _HTTP_STATUS[HealthStatus.DEGRADED] == 200

    def test_unhealthy_maps_to_503(self):
        assert _HTTP_STATUS[HealthStatus.UNHEALTHY] == 503

    def test_all_statuses_are_covered(self):
        assert set(_HTTP_STATUS.keys()) == set(HealthStatus)


# =============================================================================
# /health/live and /health/ready — router-level integration
# =============================================================================


@pytest.mark.unit
class TestLivenessEndpoint:
    """GET /health/live must always return 200 with status=alive."""

    def test_returns_200(self, health_client):
        r = health_client.get("/health/live")
        assert r.status_code == 200

    def test_body_status_is_alive(self, health_client):
        r = health_client.get("/health/live")
        assert r.json()["status"] == "alive"

    def test_does_not_check_dependencies(self, health_client):
        """Liveness must not touch any external system — verified by ensuring
        it returns 200 even when all check functions are broken."""
        with patch("health.checks._ping_db_async", new_callable=AsyncMock,
                   side_effect=RuntimeError("db down")):
            r = health_client.get("/health/live")
        assert r.status_code == 200


@pytest.mark.unit
class TestReadinessEndpoint:
    """GET /health/ready reflects real check results via mocked check functions."""

    async def test_returns_200_when_all_healthy(self, health_client):
        mongo, oll, words = _healthy_checks()
        with patch("health.router.check_mongodb",     AsyncMock(return_value=mongo)), \
             patch("health.router.check_ollama",       AsyncMock(return_value=oll)), \
             patch("health.router.check_words_filter", AsyncMock(return_value=words)):
            r = health_client.get("/health/ready")
        assert r.status_code == 200

    async def test_body_status_healthy(self, health_client):
        mongo, oll, words = _healthy_checks()
        with patch("health.router.check_mongodb",     AsyncMock(return_value=mongo)), \
             patch("health.router.check_ollama",       AsyncMock(return_value=oll)), \
             patch("health.router.check_words_filter", AsyncMock(return_value=words)):
            r = health_client.get("/health/ready")
        assert r.json()["status"] == "healthy"

    async def test_returns_503_when_mongodb_unhealthy(self, health_client):
        mongo = MongoDBCheck(status=HealthStatus.UNHEALTHY, error="down")
        oll   = OllamaCheck(status=HealthStatus.HEALTHY, model="qwen2.5:7b",
                            latency_ms=5.0, circuit_breaker="closed")
        words = WordsFilterCheck(status=HealthStatus.HEALTHY, entries=100,
                                 refresh_task_alive=True)
        with patch("health.router.check_mongodb",     AsyncMock(return_value=mongo)), \
             patch("health.router.check_ollama",       AsyncMock(return_value=oll)), \
             patch("health.router.check_words_filter", AsyncMock(return_value=words)):
            r = health_client.get("/health/ready")
        assert r.status_code == 503
        assert r.json()["status"] == "unhealthy"

    async def test_returns_200_when_ollama_degraded(self, health_client):
        """Degraded Ollama → overall degraded → still HTTP 200 (service partially functional)."""
        mongo = MongoDBCheck(status=HealthStatus.HEALTHY, latency_ms=1.0)
        oll   = OllamaCheck(status=HealthStatus.DEGRADED, model="qwen2.5:7b",
                            latency_ms=5.0, circuit_breaker="closed",
                            error="model not in local library")
        words = WordsFilterCheck(status=HealthStatus.HEALTHY, entries=100,
                                 refresh_task_alive=True)
        with patch("health.router.check_mongodb",     AsyncMock(return_value=mongo)), \
             patch("health.router.check_ollama",       AsyncMock(return_value=oll)), \
             patch("health.router.check_words_filter", AsyncMock(return_value=words)):
            r = health_client.get("/health/ready")
        assert r.status_code == 200
        assert r.json()["status"] == "degraded"

    async def test_response_contains_version(self, health_client):
        mongo, oll, words = _healthy_checks()
        with patch("health.router.check_mongodb",     AsyncMock(return_value=mongo)), \
             patch("health.router.check_ollama",       AsyncMock(return_value=oll)), \
             patch("health.router.check_words_filter", AsyncMock(return_value=words)):
            r = health_client.get("/health/ready")
        assert "version" in r.json()

    async def test_response_contains_uptime_seconds(self, health_client):
        mongo, oll, words = _healthy_checks()
        with patch("health.router.check_mongodb",     AsyncMock(return_value=mongo)), \
             patch("health.router.check_ollama",       AsyncMock(return_value=oll)), \
             patch("health.router.check_words_filter", AsyncMock(return_value=words)):
            r = health_client.get("/health/ready")
        body = r.json()
        assert "uptime_seconds" in body
        assert body["uptime_seconds"] >= 0

    async def test_response_contains_checks_object(self, health_client):
        mongo, oll, words = _healthy_checks()
        with patch("health.router.check_mongodb",     AsyncMock(return_value=mongo)), \
             patch("health.router.check_ollama",       AsyncMock(return_value=oll)), \
             patch("health.router.check_words_filter", AsyncMock(return_value=words)):
            r = health_client.get("/health/ready")
        checks = r.json()["checks"]
        assert "mongodb"      in checks
        assert "ollama"       in checks
        assert "words_filter" in checks

    async def test_each_check_called_exactly_once_per_request(self, health_client):
        """All three check coroutines must be awaited exactly once per request."""
        mongo, oll, words = _healthy_checks()
        mongo_mock = AsyncMock(return_value=mongo)
        oll_mock   = AsyncMock(return_value=oll)
        words_mock = AsyncMock(return_value=words)

        with patch("health.router.check_mongodb",     mongo_mock), \
             patch("health.router.check_ollama",       oll_mock), \
             patch("health.router.check_words_filter", words_mock):
            health_client.get("/health/ready")

        mongo_mock.assert_called_once()
        oll_mock.assert_called_once()
        words_mock.assert_called_once()
