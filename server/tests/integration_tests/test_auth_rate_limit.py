"""Integration tests for auth endpoint rate limiting.

Verifies that /auth/login and /auth/register enforce per-IP request limits,
return well-formed 429 responses, and track counters independently per client.

Design notes:
  - The rate limit storage is reset before each test by the shared `app_client`
    fixture in conftest.py, so tests are fully isolated from each other.
  - Request bodies intentionally use wrong credentials / duplicate emails.
    The responses will be 401/409 within the limit and 429 once exceeded.
    We only care that the Nth+1 request becomes 429 regardless of the Nth's
    status code — the limiter fires before the handler's auth logic.
  - IP isolation tests use httpx.ASGITransport(client=("ip", port)) to set
    request.client.host directly — the same field get_remote_address reads in
    production.  This is more correct than patching internals of the library.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest
from limits import parse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import config_manager
from core.rate_limit import limiter

# ---------------------------------------------------------------------------
# Module-level constants — derived from config so tests stay valid if the
# operator changes the defaults.
# ---------------------------------------------------------------------------

_LOGIN_LIMIT    = parse(config_manager.auth.login_rate_limit).amount
_REGISTER_LIMIT = parse(config_manager.auth.register_rate_limit).amount

# A valid form-encoded login body (credentials are intentionally wrong).
# Must be valid enough that FastAPI doesn't return 422 before the limiter fires.
_LOGIN_FORM = {"username": "nobody@example.com", "password": "wrongpassword"}

# A valid JSON register body (email may already exist — that's fine).
_REGISTER_JSON = {"email": "ratelimit@example.com", "password": "Password123!"}


# =============================================================================
# POST /auth/login
# =============================================================================


@pytest.mark.integration
class TestLoginRateLimit:

    def test_requests_within_limit_are_not_rate_limited(self, app_client):
        client, _ = app_client
        for _ in range(_LOGIN_LIMIT):
            res = client.post("/auth/login", data=_LOGIN_FORM)
            assert res.status_code != 429, (
                f"Request within the limit returned 429 (limit={_LOGIN_LIMIT})"
            )

    def test_request_exceeding_limit_returns_429(self, app_client):
        client, _ = app_client
        for _ in range(_LOGIN_LIMIT):
            client.post("/auth/login", data=_LOGIN_FORM)
        res = client.post("/auth/login", data=_LOGIN_FORM)
        assert res.status_code == 429

    def test_429_body_matches_project_error_shape(self, app_client):
        client, _ = app_client
        for _ in range(_LOGIN_LIMIT):
            client.post("/auth/login", data=_LOGIN_FORM)
        res = client.post("/auth/login", data=_LOGIN_FORM)
        assert res.status_code == 429
        body = res.json()
        assert "detail" in body, "429 body must have a 'detail' key (FastAPI convention)"
        assert isinstance(body["detail"], str) and body["detail"]

    def test_429_response_has_retry_after_header(self, app_client):
        client, _ = app_client
        for _ in range(_LOGIN_LIMIT):
            client.post("/auth/login", data=_LOGIN_FORM)
        res = client.post("/auth/login", data=_LOGIN_FORM)
        assert res.status_code == 429
        assert "retry-after" in res.headers, "RFC 6585 requires Retry-After on 429"

    def test_retry_after_value_is_a_positive_integer(self, app_client):
        client, _ = app_client
        for _ in range(_LOGIN_LIMIT):
            client.post("/auth/login", data=_LOGIN_FORM)
        res = client.post("/auth/login", data=_LOGIN_FORM)
        retry_after = res.headers.get("retry-after", "")
        assert retry_after.isdigit() and int(retry_after) > 0


# =============================================================================
# POST /auth/register
# =============================================================================


@pytest.mark.integration
class TestRegisterRateLimit:

    def test_requests_within_limit_are_not_rate_limited(self, app_client):
        client, _ = app_client
        for _ in range(_REGISTER_LIMIT):
            res = client.post("/auth/register", json=_REGISTER_JSON)
            assert res.status_code != 429, (
                f"Request within the limit returned 429 (limit={_REGISTER_LIMIT})"
            )

    def test_request_exceeding_limit_returns_429(self, app_client):
        client, _ = app_client
        for _ in range(_REGISTER_LIMIT):
            client.post("/auth/register", json=_REGISTER_JSON)
        res = client.post("/auth/register", json=_REGISTER_JSON)
        assert res.status_code == 429

    def test_429_body_matches_project_error_shape(self, app_client):
        client, _ = app_client
        for _ in range(_REGISTER_LIMIT):
            client.post("/auth/register", json=_REGISTER_JSON)
        res = client.post("/auth/register", json=_REGISTER_JSON)
        assert res.status_code == 429
        body = res.json()
        assert "detail" in body
        assert isinstance(body["detail"], str) and body["detail"]

    def test_429_response_has_retry_after_header(self, app_client):
        client, _ = app_client
        for _ in range(_REGISTER_LIMIT):
            client.post("/auth/register", json=_REGISTER_JSON)
        res = client.post("/auth/register", json=_REGISTER_JSON)
        assert res.status_code == 429
        assert "retry-after" in res.headers


# =============================================================================
# Per-IP counter isolation
# =============================================================================


@pytest.fixture(autouse=False)
def _clean_state(_global_test_setup):
    """Reset rate-limit counters and DB collections between IP-isolation tests."""
    from core.database import pool
    from config import config_manager as _cfg

    limiter._storage.reset()
    try:
        pool.get_collection(_cfg.db.events_collection).delete_many({})
        pool.get_collection("children").delete_many({})
        pool.get_collection(_cfg.db.words_collection).delete_many({})
    except Exception:
        pass


@pytest.mark.integration
class TestRateLimitIpIsolation:
    """Use httpx.ASGITransport(client=("ip", port)) to set request.client.host
    directly — the same field get_remote_address reads in production.
    This is more correct than patching library internals."""

    async def test_exhausting_one_ip_does_not_affect_another(self, _app, _clean_state):
        """Two distinct clients must have completely independent counters."""

        transport_a = httpx.ASGITransport(app=_app, client=("10.0.0.1", 9001))
        transport_b = httpx.ASGITransport(app=_app, client=("10.0.0.2", 9002))

        # Exhaust the limit for IP A.
        async with httpx.AsyncClient(transport=transport_a, base_url="http://test") as client_a:
            for _ in range(_LOGIN_LIMIT):
                await client_a.post("/auth/login", data=_LOGIN_FORM)
            blocked = await client_a.post("/auth/login", data=_LOGIN_FORM)
        assert blocked.status_code == 429

        # IP B must still have its full quota — first request must not be 429.
        async with httpx.AsyncClient(transport=transport_b, base_url="http://test") as client_b:
            res = await client_b.post("/auth/login", data=_LOGIN_FORM)
        assert res.status_code != 429

    async def test_same_ip_shares_one_counter_across_requests(self, _app, _clean_state):
        """Requests from the same IP must all draw from a single shared counter."""

        transport = httpx.ASGITransport(app=_app, client=("192.168.1.100", 9003))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(_LOGIN_LIMIT):
                await client.post("/auth/login", data=_LOGIN_FORM)
            res = await client.post("/auth/login", data=_LOGIN_FORM)

        assert res.status_code == 429
