from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from auth import repository as auth_repo
from auth.dependencies import get_current_user
from auth.security import hash_token
from config import config_manager
from core.schemas import OkResponse
from notifications import telegram as tg
from telegram import repository as tg_repo

log = logging.getLogger(__name__)

router = APIRouter(tags=["telegram"])

_LINK_TOKEN_TTL_MINUTES = 10


class TelegramLinkResponse(BaseModel):
    url: str


@router.post("/api/me/telegram/link", response_model=TelegramLinkResponse)
def telegram_link(current_user: dict = Depends(get_current_user)) -> TelegramLinkResponse:
    """Generate a one-time deep-link URL the parent opens in Telegram to connect their account."""
    if not config_manager.telegram.bot_username:
        raise HTTPException(status_code=503, detail="Telegram integration not configured.")

    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_LINK_TOKEN_TTL_MINUTES)
    tg_repo.upsert_link_token(current_user["id"], hash_token(token), expires_at)

    bot = config_manager.telegram.bot_username
    return TelegramLinkResponse(url=f"https://t.me/{bot}?start={token}")


@router.post("/api/telegram/webhook", include_in_schema=False, response_model=OkResponse)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
) -> OkResponse:
    """Telegram update webhook — receives messages sent to the bot."""
    expected = config_manager.telegram.webhook_secret
    if expected and x_telegram_bot_api_secret_token != expected:
        raise HTTPException(status_code=403, detail="Forbidden.")

    update = await request.json()
    message = update.get("message") or update.get("edited_message")
    if not message:
        return OkResponse()

    text: str = message.get("text", "")
    chat_id: int = message["chat"]["id"]

    if not text.startswith("/start"):
        return OkResponse()

    # Deep-link format: /start <token>  (token absent when parent opens bot directly)
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return OkResponse()

    token = parts[1].strip()
    user_id = tg_repo.consume_link_token(hash_token(token))
    if not user_id:
        log.info("telegram_webhook: unknown or expired link token  chat_id=%s", chat_id)
        return OkResponse()

    auth_repo.update_telegram_chat_id(user_id, str(chat_id))
    log.info("Telegram linked  user=%r  chat_id=%s", user_id, chat_id)

    try:
        await tg.send_message(chat_id=chat_id, text="HopMap notifications connected!")
    except Exception:
        log.warning("Could not send Telegram confirmation  chat_id=%s", chat_id)

    return OkResponse()
