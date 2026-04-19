import asyncio
import logging
import time

from classify.circuit_breaker import LLMCircuitBreaker
from classify.exceptions import LLMCircuitOpenError, LLMTimeoutError, LLMUnavailableError
from config import config_manager
from llm import LLMProvider
from words.service import check_blocked_words

log = logging.getLogger(__name__)

# Transient errors worth retrying — availability and timeout issues only.
# LLMInferenceError and LLMResponseParseError are deterministic; retrying
# them would just reproduce the same failure.
_RETRYABLE_ERRORS = (LLMUnavailableError, LLMTimeoutError)
_MAX_RETRIES      = 2
_RETRY_BASE_DELAY = 0.5  # seconds; actual delays: 0.5 s, 1.0 s

_circuit_breaker = LLMCircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

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


def get_circuit_breaker_state() -> str:
    return _circuit_breaker.state


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
    """Classify *context* with retry and circuit-breaker for transient LLM failures.

    Retries up to _MAX_RETRIES times with exponential backoff on
    LLMUnavailableError and LLMTimeoutError.  If the circuit breaker is OPEN,
    the call fails immediately without sleeping — callers receive
    LLMCircuitOpenError (a subclass of LLMUnavailableError).
    """
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES + 1):
        if attempt:
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))  # 0.5 s, 1.0 s
            log.warning("LLM classify retry %d/%d  delay=%.1fs", attempt, _MAX_RETRIES, delay)
            await asyncio.sleep(delay)

        try:
            return await _circuit_breaker.call(
                lambda: asyncio.to_thread(_llm.classify, context, _CLASSIFY_SYSTEM_PROMPT)
            )
        except LLMCircuitOpenError:
            raise  # Circuit is open — sleeping and retrying won't help
        except _RETRYABLE_ERRORS as exc:
            last_exc = exc
        # LLMInferenceError, LLMResponseParseError — not caught here, propagate immediately

    assert last_exc is not None  # loop ran at least once; last_exc set by _RETRYABLE_ERRORS catch
    raise last_exc


