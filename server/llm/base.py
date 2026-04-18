"""Abstract base class for all LLM classification providers."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Interface every LLM backend must implement.

    Subclasses call their respective API and return a structured dict.
    All async wrapping (``asyncio.to_thread``) and HTTP error handling
    live in server.py — providers only need to worry about inference.
    """

    @abstractmethod
    def classify(self, context: str, system_prompt: str) -> dict:
        """Run the model and return a classification result.

        Args:
            context:       Chat snippet + URL to classify.
            system_prompt: Full system instruction string.

        Returns:
            Dict with keys:
                decision   (str)  — ``"YES"`` or ``"NO"``
                confidence (int)  — 0–100
                reason     (str)  — short human-readable phrase

        Raises:
            json.JSONDecodeError: if the model response is not valid JSON.
            Exception:           for any provider-level failure (network, auth, etc.).
        """

    # ------------------------------------------------------------------
    # Shared helper — available to every subclass
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """Parse raw model output into a validated classification dict.

        Strips markdown code fences that some models emit despite explicit
        instructions not to, then validates the three required fields.
        Raises ``json.JSONDecodeError`` on malformed output so callers can
        catch it and return a safe fallback.
        """
        raw = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE
        ).strip()
        data = json.loads(raw)
        decision = str(data.get("decision", "NO")).upper()
        if decision not in {"YES", "NO"}:
            decision = "NO"
        return {
            "decision":   decision,
            "confidence": max(0, min(100, int(data.get("confidence", 50)))),
            "reason":     str(data.get("reason", "")).strip(),
        }
