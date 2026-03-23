"""LLM provider registry for HopMap.

How to add a new provider
─────────────────────────
1. Create a module in this package, e.g. ``openai_provider.py``.
2. Subclass :class:`~llm.base.LLMProvider` and implement ``classify()``.
3. Add an import and a branch in :func:`get_provider` below.
4. Set ``LLM_PROVIDER=<name>`` (and any new credentials) in ``.env``.

That's it — no changes needed anywhere else in the server.
"""

from __future__ import annotations

from .base import LLMProvider
from .ollama_provider import OllamaProvider

__all__ = ["LLMProvider", "get_provider"]


def get_provider(name: str, model: str) -> LLMProvider:
    """Instantiate and return the configured LLM provider.

    Args:
        name:  Value of the ``LLM_PROVIDER`` env-var (e.g. ``"ollama"``).
        model: Model identifier passed through to the provider.

    Raises:
        ValueError: if *name* does not match any registered provider.
    """
    if name == "ollama":
        return OllamaProvider(model=model)

    # ── Add future providers here ──────────────────────────────────────
    # if name == "openai":
    #     from .openai_provider import OpenAIProvider
    #     return OpenAIProvider(model=model)
    #
    # if name == "anthropic":
    #     from .anthropic_provider import AnthropicProvider
    #     return AnthropicProvider(model=model)
    # ──────────────────────────────────────────────────────────────────

    raise ValueError(
        f"Unknown LLM_PROVIDER {name!r}.  "
        f"Supported: 'ollama'.  "
        f"See backend/server/llm/__init__.py to register a new one."
    )
