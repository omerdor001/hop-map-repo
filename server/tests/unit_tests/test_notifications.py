"""Unit tests for notifications/telegram.py and notifications/service.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch  # AsyncMock kept for dispatch_hop mocks

import pytest

_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from notifications.telegram import TelegramError, send_message
from notifications.service import dispatch_hop


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _http_mock(status_code: int, body: dict | None = None):
    """Return (sync-context-manager, inner-http-client) with a canned response.

    Both resp.content and resp.json() are derived from the same dict so mocked
    behaviour is internally consistent.
    """
    body = body or {}
    resp = MagicMock(status_code=status_code)
    resp.content = json.dumps(body).encode()
    resp.json.return_value = body
    resp.text = json.dumps(body)
    http = MagicMock()
    http.post = MagicMock(return_value=resp)
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=http)
    cm.__exit__ = MagicMock(return_value=None)
    return cm, http


@pytest.fixture
def dispatch_mocks():
    """Patch all three external dependencies of dispatch_hop at once."""
    with patch("notifications.service.config_manager") as cfg, \
         patch("notifications.service.auth_repo") as repo, \
         patch("notifications.service.telegram") as tg:
        tg.TelegramError = TelegramError  # preserve real class so except clauses work
        yield cfg, repo, tg


# ---------------------------------------------------------------------------
# notifications.telegram.send_message
# ---------------------------------------------------------------------------

class TestSendMessage:

    async def test_posts_to_correct_telegram_url(self):
        cm, http = _http_mock(200)
        with patch("notifications.telegram.config_manager") as cfg, \
             patch("httpx.Client", return_value=cm):
            cfg.telegram.bot_token = "ABC123"
            await send_message(chat_id=42, text="hello")
        url = http.post.call_args[0][0]
        assert "botABC123/sendMessage" in url

    async def test_sends_chat_id_and_text_in_payload(self):
        cm, http = _http_mock(200)
        with patch("notifications.telegram.config_manager") as cfg, \
             patch("httpx.Client", return_value=cm):
            cfg.telegram.bot_token = "TOK"
            await send_message(chat_id=99, text="test message")
        payload = http.post.call_args[1]["json"]
        assert payload["chat_id"] == 99
        assert payload["text"] == "test message"

    async def test_raises_telegram_error_on_4xx(self):
        cm, _ = _http_mock(400, {"description": "chat not found"})
        with patch("notifications.telegram.config_manager") as cfg, \
             patch("httpx.Client", return_value=cm):
            cfg.telegram.bot_token = "TOK"
            with pytest.raises(TelegramError) as exc_info:
                await send_message(chat_id=99, text="hi")
        assert exc_info.value.status_code == 400
        assert "chat not found" in str(exc_info.value)

    async def test_raises_telegram_error_on_5xx(self):
        cm, _ = _http_mock(500, {"description": "Internal Server Error"})
        with patch("notifications.telegram.config_manager") as cfg, \
             patch("httpx.Client", return_value=cm):
            cfg.telegram.bot_token = "TOK"
            with pytest.raises(TelegramError) as exc_info:
                await send_message(chat_id=99, text="hi")
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# notifications.service.dispatch_hop
# ---------------------------------------------------------------------------

class TestDispatchHop:

    async def test_skips_entirely_when_telegram_disabled(self, dispatch_mocks):
        cfg, repo, _ = dispatch_mocks
        cfg.telegram.enabled = False
        await dispatch_hop("parent-1", "Alice", "discord.exe")
        repo.get_user_by_id.assert_not_called()

    async def test_skips_when_parent_not_found(self, dispatch_mocks):
        cfg, repo, tg = dispatch_mocks
        cfg.telegram.enabled = True
        repo.get_user_by_id.return_value = None
        await dispatch_hop("parent-x", "Alice", "discord.exe")
        tg.send_message.assert_not_called()

    async def test_skips_when_parent_has_no_chat_id(self, dispatch_mocks):
        cfg, repo, tg = dispatch_mocks
        cfg.telegram.enabled = True
        repo.get_user_by_id.return_value = {"telegramChatId": None}
        await dispatch_hop("parent-1", "Alice", "discord.exe")
        tg.send_message.assert_not_called()

    async def test_looks_up_parent_by_the_given_id(self, dispatch_mocks):
        cfg, repo, tg = dispatch_mocks
        cfg.telegram.enabled = True
        repo.get_user_by_id.return_value = {"telegramChatId": "555"}
        tg.send_message = AsyncMock()
        await dispatch_hop("specific-parent-id", "Alice", "app.exe")
        repo.get_user_by_id.assert_called_once_with("specific-parent-id")

    async def test_sends_to_parent_chat_id_with_child_and_app(self, dispatch_mocks):
        cfg, repo, tg = dispatch_mocks
        cfg.telegram.enabled = True
        repo.get_user_by_id.return_value = {"telegramChatId": "99887766"}
        tg.send_message = AsyncMock()
        await dispatch_hop("parent-1", "Alice", "discord.exe")
        tg.send_message.assert_awaited_once()
        kwargs = tg.send_message.call_args[1]
        assert kwargs["chat_id"] == "99887766"
        assert "Alice" in kwargs["text"]
        assert "discord.exe" in kwargs["text"]

    async def test_never_raises_on_telegram_error(self, dispatch_mocks):
        cfg, repo, tg = dispatch_mocks
        cfg.telegram.enabled = True
        repo.get_user_by_id.return_value = {"telegramChatId": "123"}
        tg.send_message = AsyncMock(side_effect=TelegramError("API down", 503))
        await dispatch_hop("parent-1", "Alice", "app.exe")  # must not raise

    async def test_never_raises_on_unexpected_exception(self, dispatch_mocks):
        cfg, repo, tg = dispatch_mocks
        cfg.telegram.enabled = True
        repo.get_user_by_id.return_value = {"telegramChatId": "123"}
        tg.send_message = AsyncMock(side_effect=RuntimeError("unexpected"))
        await dispatch_hop("parent-1", "Alice", "app.exe")  # must not raise
