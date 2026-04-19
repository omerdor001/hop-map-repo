"""Domain exceptions for the classification pipeline.

All LLM provider errors are translated into one of these types before they
leave the provider layer, so the router never has to import httpx or ollama.
"""

from __future__ import annotations


class ClassifyError(Exception):
    """Base for all classification-pipeline failures."""


class LLMUnavailableError(ClassifyError):
    """Ollama daemon is unreachable or the requested model is not pulled."""


class LLMTimeoutError(ClassifyError):
    """Inference request exceeded the timeout threshold."""


class LLMInferenceError(ClassifyError):
    """Ollama returned an error response during inference (e.g. 4xx/5xx)."""


class LLMResponseParseError(ClassifyError):
    """Model output could not be parsed into a valid classification dict.

    Attributes:
        raw:   The raw string the model returned (truncated to 500 chars).
        cause: The underlying parse exception.
    """

    def __init__(self, raw: str, cause: Exception) -> None:
        super().__init__(f"Unparseable LLM response: {cause}")
        self.raw = raw[:500]
        self.cause = cause


class LLMCircuitOpenError(LLMUnavailableError):
    """Raised when the circuit breaker is OPEN and calls are suppressed.

    Subclasses LLMUnavailableError so the router's existing handler catches it
    and returns the safe-NO fallback — no extra handler needed.
    """
