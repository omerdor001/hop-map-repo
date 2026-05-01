from __future__ import annotations

import logging

import httpx

from config import config_manager

log = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org"


class TelegramError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


async def send_message(chat_id: int | str, text: str) -> None:
    """Send a plain-text message via the Telegram Bot API.

    Raises TelegramError on non-2xx responses.
    """
    token = config_manager.telegram.bot_token
    url = f"{_API_BASE}/bot{token}/sendMessage"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json={"chat_id": chat_id, "text": text})

    if response.status_code >= 400:
        body = response.json() if response.content else {}
        raise TelegramError(
            f"Telegram API error: {body.get('description', response.text)}",
            status_code=response.status_code,
        )

    log.debug("Telegram message sent  chat_id=%s", chat_id)
