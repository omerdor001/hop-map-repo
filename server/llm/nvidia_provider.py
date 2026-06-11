"""NVIDIA NIM LLM provider — cloud inference via NVIDIA's OpenAI-compatible API.

Configured by:
    LLM_PROVIDER=nvidia
    LLM_MODEL=moonshotai/kimi-k2          (or any model in the NVIDIA catalog)
    HOPMAP_SERVER__LLM__API_KEY=nvapi-... (from build.nvidia.com)

NVIDIA NIM exposes an OpenAI-compatible endpoint at
``https://integrate.api.nvidia.com/v1``, so this provider reuses the
``openai`` Python SDK with a custom base URL and API key.
"""

from __future__ import annotations

import json

import openai

from classify.exceptions import (
    LLMInferenceError,
    LLMResponseParseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from .base import LLMProvider

_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# NIM inference can be slow for large models; mirror the 10-minute ceiling
# used in production JS clients.  The openai SDK accepts seconds as a float.
_TIMEOUT_SECONDS = 600.0

# SDK-level retries are intentionally disabled.  classify/service.py already
# handles LLMUnavailableError and LLMTimeoutError with exponential backoff.
# Stacking both retry layers multiplies worst-case latency: with a 600 s
# timeout, (1 + sdk_retries) × (1 + service_retries) × 600 s = 30+ minutes.
_SDK_MAX_RETRIES = 0


class NvidiaProvider(LLMProvider):
    """Calls NVIDIA NIM (OpenAI-compatible) for classification.

    ``model`` is any model tag listed in the NVIDIA catalog, e.g.
    ``"moonshotai/kimi-k2"`` or ``"meta/llama-3.1-70b-instruct"``.
    Controlled by the ``LLM_MODEL`` field in ``server_config.json``.

    ``api_key`` is your NVIDIA API key (``nvapi-...``), injected via
    ``HOPMAP_SERVER__LLM__API_KEY`` in ``.env``.

    All exceptions are translated into domain exceptions from
    ``classify.exceptions`` so callers never need to import openai directly.
    """

    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        # Singleton client — reuses the underlying HTTP connection pool for
        # the lifetime of the provider instance (one per server process).
        self._client = openai.OpenAI(
            base_url=_NVIDIA_BASE_URL,
            api_key=api_key,
            timeout=_TIMEOUT_SECONDS,
            max_retries=_SDK_MAX_RETRIES,
        )

    def classify(self, context: str, system_prompt: str) -> dict:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": context},
                ],
                temperature=0,
            )
        except openai.APIConnectionError as exc:
            raise LLMUnavailableError(
                f"Cannot reach NVIDIA NIM API (model={self.model!r})"
            ) from exc
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError(
                f"NVIDIA NIM inference timed out (model={self.model!r})"
            ) from exc
        except openai.AuthenticationError as exc:
            raise LLMInferenceError(
                f"NVIDIA API key invalid or missing (model={self.model!r}): {exc}"
            ) from exc
        except openai.NotFoundError as exc:
            # 404 — model not found in the NVIDIA catalog
            raise LLMUnavailableError(
                f"Model {self.model!r} not found in the NVIDIA NIM catalog: {exc}"
            ) from exc
        except openai.RateLimitError as exc:
            raise LLMInferenceError(
                f"NVIDIA NIM rate limit exceeded (model={self.model!r}): {exc}"
            ) from exc
        except openai.APIStatusError as exc:
            # Covers all other 4xx/5xx responses.
            raise LLMInferenceError(
                f"NVIDIA NIM error {exc.status_code} (model={self.model!r}): {exc.message}"
            ) from exc

        # Guard against unexpected response shapes before touching content.
        try:
            choice = response.choices[0]
        except (AttributeError, IndexError, TypeError) as exc:
            raise LLMResponseParseError(repr(response)[:500], exc) from exc

        # finish_reason checks — mirror the JS reference implementation.
        if choice.finish_reason == "length":
            raise LLMInferenceError(
                f"NVIDIA NIM response truncated by token limit (model={self.model!r})"
                " — consider a shorter context or a model with a larger context window"
            )
        if choice.finish_reason == "content_filter":
            raise LLMInferenceError(
                f"NVIDIA NIM response blocked by content filter (model={self.model!r})"
            )
        if choice.finish_reason not in (None, "stop"):
            raise LLMInferenceError(
                f"NVIDIA NIM returned unexpected finish_reason {choice.finish_reason!r} "
                f"(model={self.model!r})"
            )

        try:
            raw = (choice.message.content or "").strip()
        except (AttributeError, TypeError) as exc:
            raise LLMResponseParseError(repr(choice)[:500], exc) from exc

        if not raw:
            raise LLMInferenceError(
                f"NVIDIA NIM returned empty content (model={self.model!r})"
            )

        try:
            return self._parse_response(raw)
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            raise LLMResponseParseError(raw, exc) from exc
