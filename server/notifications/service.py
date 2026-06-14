from __future__ import annotations

import logging
from datetime import datetime, timezone

from auth import repository as auth_repo
from config import config_manager
from notifications import telegram

log = logging.getLogger(__name__)


def _risk_label(confidence: int | None) -> str:
    if confidence is None:
        return "Unknown"
    if confidence >= 80:
        return "High"
    if confidence >= 50:
        return "Medium"
    return "Low"


async def dispatch_hop(
    parent_id: str,
    child_name: str,
    to_app: str,
    from_app: str = "",
    to_title: str = "",
    from_title: str = "",
    timestamp: str = "",
    confidence: int | None = None,
) -> None:
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

    to_label   = to_title   or to_app
    from_label = from_title or from_app

    try:
        dt = datetime.fromisoformat(timestamp).astimezone(timezone.utc)
        time_str = dt.strftime("%I:%M %p UTC").lstrip("0")
    except Exception:
        time_str = ""

    risk = _risk_label(confidence)
    risk_emoji = "🔴" if risk == "High" else "🟡" if risk == "Medium" else "🟢" if risk == "Low" else "⚪"

    lines = [f"🚨 HopMap Alert — {child_name}"]
    if from_label:
        lines.append(f"📤 From: {from_label}")
    lines.append(f"📥 To: {to_label}")
    if time_str:
        lines.append(f"🕐 {time_str}")
    lines.append(f"{risk_emoji} Risk: {risk}" + (f" ({confidence}%)" if confidence is not None else ""))

    text = "\n".join(lines)
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
