"""
Integration tests for POST /agent/activate.

Uses the mocked TestClient (app_client fixture from conftest.py).  Each test
registers a child via POST /api/children, then manually seeds a setup code
via the repository layer to avoid depending on GET /agent/installer.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from auth.security import hash_token
from children.repository import get_child_by_agent_token, upsert_setup_code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_setup_code(child_id: str, setup_code: str, *, ttl_hours: float = 1.0) -> None:
    """Write a setup code directly to the DB, bypassing the HTTP layer."""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    upsert_setup_code(child_id, hash_token(setup_code), expires_at)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAgentActivate:

    def test_valid_setup_code_returns_agent_token(self, app_client):
        """A valid, unexpired setup code returns a fresh agent token."""
        client, _ = app_client
        res = client.post("/api/children", json={"childName": "Alice"})
        res.raise_for_status()
        child_id = res.json()["childId"]

        _seed_setup_code(child_id, "valid-code-abc")

        res = client.post("/agent/activate", json={"setupCode": "valid-code-abc"})
        assert res.status_code == 200
        data = res.json()
        assert "agentToken" in data
        assert len(data["agentToken"]) == 64  # secrets.token_hex(32)

    def test_agent_token_is_stored_in_db(self, app_client):
        """After activation the new token hash is findable in the DB."""
        client, _ = app_client
        res = client.post("/api/children", json={"childName": "Bob"})
        res.raise_for_status()
        child_id = res.json()["childId"]
        _seed_setup_code(child_id, "code-for-bob")

        activate_res = client.post("/agent/activate", json={"setupCode": "code-for-bob"})
        token = activate_res.json()["agentToken"]

        child = get_child_by_agent_token(hash_token(token))
        assert child is not None
        assert child["childId"] == child_id

    def test_expired_setup_code_returns_400(self, app_client):
        """An expired setup code is rejected with 400."""
        client, _ = app_client
        res = client.post("/api/children", json={"childName": "Carol"})
        res.raise_for_status()
        child_id = res.json()["childId"]

        _seed_setup_code(child_id, "expired-code", ttl_hours=-1.0)

        res = client.post("/agent/activate", json={"setupCode": "expired-code"})
        assert res.status_code == 400

    def test_unknown_setup_code_returns_400(self, app_client):
        """A code that was never issued returns the same 400 — no oracle leak."""
        client, _ = app_client
        res = client.post("/agent/activate", json={"setupCode": "totally-unknown-code"})
        assert res.status_code == 400

    def test_setup_code_is_single_use(self, app_client):
        """After a successful activation the same code returns 400."""
        client, _ = app_client
        res = client.post("/api/children", json={"childName": "Dave"})
        res.raise_for_status()
        child_id = res.json()["childId"]

        _seed_setup_code(child_id, "single-use-code")

        first = client.post("/agent/activate", json={"setupCode": "single-use-code"})
        assert first.status_code == 200

        second = client.post("/agent/activate", json={"setupCode": "single-use-code"})
        assert second.status_code == 400

    def test_old_token_not_in_db_after_activation(self, app_client):
        """The token from POST /api/children is no longer in the DB after activation."""
        client, _ = app_client
        register_res = client.post("/api/children", json={"childName": "Eve"})
        register_res.raise_for_status()
        child_id = register_res.json()["childId"]
        old_token = register_res.json()["agentToken"]

        _seed_setup_code(child_id, "eve-setup-code")
        client.post("/agent/activate", json={"setupCode": "eve-setup-code"})

        assert get_child_by_agent_token(hash_token(old_token)) is None
