"""Ollama LLM provider — local inference via the Ollama desktop client.

Configured by:
    OLLAMA_MODEL=qwen2.5:7b   (or any model you have pulled locally)

The Ollama daemon must be running on the server machine.
"""

from __future__ import annotations

import json

import httpx
import ollama

from classify.exceptions import (
    LLMInferenceError,
    LLMResponseParseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from .base import LLMProvider


class OllamaProvider(LLMProvider):
    """Calls a locally running Ollama model for classification.

    ``model`` is the Ollama model tag, e.g. ``"qwen2.5:7b"``.
    Controlled by the ``OLLAMA_MODEL`` env-var in ``.env``.

    All provider-level exceptions are translated into domain exceptions
    from ``classify.exceptions`` so callers never need to import httpx
    or the ollama library directly.
    """

    def __init__(self, model: str) -> None:
        self.model = model

    def classify(self, context: str, system_prompt: str) -> dict:
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": context},
                ],
                options={"temperature": 0},
            )
        except httpx.ConnectError as exc:
            raise LLMUnavailableError(
                f"Cannot reach Ollama daemon (model={self.model!r})"
            ) from exc
        except httpx.TimeoutException as exc:
            # Covers ConnectTimeout, ReadTimeout, WriteTimeout, PoolTimeout.
            raise LLMTimeoutError(
                f"Ollama inference timed out (model={self.model!r})"
            ) from exc
        except httpx.NetworkError as exc:
            # ReadError, WriteError, CloseError — transport-level failures.
            raise LLMUnavailableError(
                f"Network error reaching Ollama (model={self.model!r})"
            ) from exc
        except httpx.RemoteProtocolError as exc:
            # Daemon was reached but returned invalid HTTP — treat as an
            # inference error, not unavailability.
            raise LLMInferenceError(
                f"Ollama returned invalid HTTP (model={self.model!r}): {exc}"
            ) from exc
        except ollama.ResponseError as exc:
            # 404 means the model hasn't been pulled yet — operators need a
            # clear signal to run `ollama pull`, not a generic inference error.
            if exc.status_code == 404:
                raise LLMUnavailableError(
                    f"Model {self.model!r} not found in Ollama"
                    f" — run: ollama pull {self.model}"
                ) from exc
            raise LLMInferenceError(
                f"Ollama error {exc.status_code} (model={self.model!r}): {exc}"
            ) from exc

        # Extract raw content — wrap structural surprises in the same domain
        # exception so nothing escapes the boundary as a plain KeyError.
        try:
            raw = response["message"]["content"].strip()
        except (KeyError, AttributeError, TypeError) as exc:
            raise LLMResponseParseError(repr(response)[:500], exc) from exc

        try:
            return self._parse_response(raw)
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            raise LLMResponseParseError(raw, exc) from exc
