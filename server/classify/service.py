import asyncio
import json
import logging
import time

from config import config_manager
from llm import LLMProvider
from words.service import check_blocked_words

log = logging.getLogger(__name__)

_CLASSIFY_SYSTEM_PROMPT = """\
You are a child-safety monitor reviewing in-game chat messages for predatory behavior, hate speech, and inappropriate content.

Reply YES if the message contains ANY of the following:
 - OFF-PLATFORMING: Links or handles for Discord, Telegram, Snap, Instagram, WhatsApp, TikTok, etc.; requests to "move to DMs", "friend me on Discord", "join my server", "add me on [platform]", or "voice chat elsewhere."
 - FREE-ITEM LURE: Promises of free Robux, skins, items, or in-game currency contingent on joining an external platform or clicking a link.
 - HATE SPEECH / ANTISEMITISM: Any slur, dehumanizing language, or tropes targeting Jewish people or any other protected group (race, religion, gender, identity).
 - SEXUAL CONTENT: Explicit language, requests for ERP (Erotic Roleplay), sexualized comments about avatars, or requests for photos.
 - GROOMING / INTRUSIVE QUESTIONS: Asking for age, real-world location (city, school, country), phone number, or whether the child is alone at home.

Reply NO if:
 - The link is an official game resource (wiki, patch notes, Roblox Help Center, Minecraft.net, Steam store page).
 - The chat is strictly about gameplay, strategy, or in-game item trading with no external-platform element.
 - The language is competitive (trash talk) but contains no slurs and no predatory intent.

Respond with a JSON object ONLY — no markdown, no explanation, no extra text.
Schema:
{
  "decision":   "YES" or "NO",
  "confidence": integer 0-100,
  "reason":     "one short phrase describing the violation (max 10 words)"
}
"""

# { child_id: [monotonic_timestamp, …] }
_classify_call_times: dict[str, list[float]] = {}
_classify_rate_lock = asyncio.Lock()

_llm: LLMProvider | None = None


def set_llm(provider: LLMProvider) -> None:
    global _llm
    _llm = provider


async def check_rate_limit(child_id: str) -> bool:
    now = time.monotonic()
    async with _classify_rate_lock:
        recent = [t for t in _classify_call_times.get(child_id, []) if now - t < 60.0]
        if len(recent) >= config_manager.classify_max_rpm:
            _classify_call_times[child_id] = recent
            return False
        recent.append(now)
        _classify_call_times[child_id] = recent
        return True


async def run_classify(context: str) -> dict:
    """Run LLM classification in a thread (non-blocking)."""
    return await asyncio.to_thread(_llm.classify, context, _CLASSIFY_SYSTEM_PROMPT)


