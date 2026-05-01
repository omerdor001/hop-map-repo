from __future__ import annotations

import logging

from auth import repository as auth_repo
from config import config_manager
from notifications import telegram

log = logging.getLogger(__name__)


async def dispatch_hop(parent_id: str, child_name: str, to_app: str) -> None:
    """Send a Telegram notification to the parent for a confirmed hop event.

    Silently skips when Telegram is not configured or the parent has no chat ID set.
    Never raises — failures are logged so the caller (hop endpoint) is unaffected.
    """
    if not config_manager.telegram.enabled:
        return

    parent = auth_repo.get_user_by_id(parent_id)
    if not parent:
        log.warning("dispatch_hop: parent %r not found", parent_id)
        return

    chat_id: str | None = parent.get("telegramChatId")
    if not chat_id:
        return

    text = f"HopMap alert: {child_name} switched to {to_app}"
    try:
        await telegram.send_message(chat_id=chat_id, text=text)
        log.info("Telegram hop notification sent  parent=%r  app=%r", parent_id, to_app)
    except telegram.TelegramError as exc:
        log.error(
            "Telegram send failed  parent=%r  status=%s  error=%s",
            parent_id, exc.status_code, exc,
        )
    except Exception:
        log.exception("Unexpected error sending Telegram notification  parent=%r", parent_id)
