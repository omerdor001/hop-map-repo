"""Integration tests for the Telegram deep-link flow.

POST /api/me/telegram/link  — generates a one-time deep-link URL
POST /api/telegram/webhook  — receives Telegram updates, links accounts
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from auth.repository import create_user
from auth.security import hash_token
from config import config_manager
from core.database import pool
from telegram.repository import upsert_link_token


# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_state():
    """Wipe users and link tokens before and after each test."""
    pool.get_collection("users").delete_many({})
    pool.get_collection("telegram_link_tokens").delete_many({})
    yield
    pool.get_collection("users").delete_many({})
    pool.get_collection("telegram_link_tokens").delete_many({})


@pytest.fixture(autouse=True)
def _mock_send():
    """Prevent any real HTTP call to Telegram in all tests in this module."""
    with patch("notifications.telegram.send_message", new_callable=AsyncMock) as mock:
        yield mock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_token(user_id: str, raw_token: str, *, ttl_minutes: float = 10.0) -> None:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    upsert_link_token(user_id, hash_token(raw_token), expires)


# ---------------------------------------------------------------------------
# POST /api/me/telegram/link
# ---------------------------------------------------------------------------

class TestTelegramLink:

    def test_returns_telegram_deep_link_url(self, app_client):
        client, _ = app_client
        with patch.object(config_manager.telegram, "bot_username", "HopMapBot"):
            resp = client.post("/api/me/telegram/link")
        assert resp.status_code == 200
        assert resp.json()["url"].startswith("https://t.me/HopMapBot?start=")

    def test_each_call_returns_a_different_token(self, app_client):
        client, _ = app_client
        with patch.object(config_manager.telegram, "bot_username", "HopMapBot"):
            url1 = client.post("/api/me/telegram/link").json()["url"]
            url2 = client.post("/api/me/telegram/link").json()["url"]
        assert url1 != url2

    def test_returns_503_when_bot_username_not_configured(self, app_client):
        client, _ = app_client
        with patch.object(config_manager.telegram, "bot_username", ""):
            resp = client.post("/api/me/telegram/link")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# POST /api/telegram/webhook
# ---------------------------------------------------------------------------

class TestTelegramWebhook:

    @pytest.fixture(autouse=True)
    def _clear_webhook_secret(self):
        """Ensure no ambient webhook_secret from .env interferes with these tests."""
        with patch.object(config_manager.telegram, "webhook_secret", ""):
            yield

    def _post(self, client, update: dict, secret: str | None = None):
        headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret else {}
        return client.post("/api/telegram/webhook", json=update, headers=headers)

    def _start_update(self, chat_id: int, token: str) -> dict:
        return {"message": {"chat": {"id": chat_id}, "text": f"/start {token}"}}

    # ── happy path ───────────────────────────────────────────────────────────

    def test_valid_token_stores_chat_id_in_db(self, app_client, _mock_send):
        client, _ = app_client
        user_id = create_user("tg-link@test.com", "hash", "TG Test")
        _seed_token(user_id, "link-token-xyz")

        resp = self._post(client, self._start_update(555666, "link-token-xyz"))

        assert resp.status_code == 200
        doc = pool.get_collection("users").find_one({"telegramChatId": "555666"})
        assert doc is not None

    def test_sends_confirmation_message_to_linked_chat(self, app_client, _mock_send):
        client, _ = app_client
        user_id = create_user("tg-confirm@test.com", "hash", "TG Confirm")
        _seed_token(user_id, "confirm-token")

        self._post(client, self._start_update(444555, "confirm-token"))

        _mock_send.assert_awaited_once()
        assert _mock_send.call_args[1]["chat_id"] == 444555

    def test_token_is_single_use(self, app_client, _mock_send):
        client, _ = app_client
        user_id = create_user("tg-once@test.com", "hash", "TG Once")
        _seed_token(user_id, "single-use-tg")

        self._post(client, self._start_update(777, "single-use-tg"))
        self._post(client, self._start_update(888, "single-use-tg"))

        doc = pool.get_collection("users").find_one({"telegramChatId": "888"})
        assert doc is None

    # ── silent-ignore cases ──────────────────────────────────────────────────

    def test_expired_token_returns_ok_without_linking(self, app_client, _mock_send):
        client, _ = app_client
        _seed_token("any-user", "expired-tok", ttl_minutes=-1.0)

        resp = self._post(client, self._start_update(999, "expired-tok"))

        assert resp.status_code == 200
        _mock_send.assert_not_awaited()

    def test_unknown_token_returns_ok_without_linking(self, app_client, _mock_send):
        client, _ = app_client
        resp = self._post(client, self._start_update(999, "totally-unknown"))
        assert resp.status_code == 200
        _mock_send.assert_not_awaited()

    def test_non_start_message_is_ignored(self, app_client):
        client, _ = app_client
        resp = self._post(client, {"message": {"chat": {"id": 1}, "text": "hello"}})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_start_without_token_is_ignored(self, app_client, _mock_send):
        client, _ = app_client
        resp = self._post(client, {"message": {"chat": {"id": 1}, "text": "/start"}})
        assert resp.status_code == 200
        _mock_send.assert_not_awaited()

    def test_update_with_no_message_field_is_ignored(self, app_client):
        client, _ = app_client
        resp = self._post(client, {"callback_query": {"id": "abc"}})
        assert resp.status_code == 200

    # ── webhook secret verification ──────────────────────────────────────────

    def test_wrong_secret_returns_403(self, app_client):
        client, _ = app_client
        with patch.object(config_manager.telegram, "webhook_secret", "correct-secret"):
            resp = self._post(
                client,
                {"message": {"chat": {"id": 1}, "text": "/start x"}},
                secret="wrong-secret",
            )
        assert resp.status_code == 403

    def test_correct_secret_is_not_rejected(self, app_client):
        client, _ = app_client
        with patch.object(config_manager.telegram, "webhook_secret", "my-secret"):
            resp = self._post(
                client,
                {"message": {"chat": {"id": 1}, "text": "/start x"}},
                secret="my-secret",
            )
        assert resp.status_code == 200

    def test_empty_webhook_secret_disables_verification(self, app_client):
        client, _ = app_client
        with patch.object(config_manager.telegram, "webhook_secret", ""):
            resp = self._post(client, {"message": {"chat": {"id": 1}, "text": "/start x"}})
        assert resp.status_code == 200
