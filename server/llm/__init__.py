"""LLM provider registry for HopMap.

How to add a new provider
─────────────────────────
1. Create a module in this package, e.g. ``openai_provider.py``.
2. Subclass :class:`~llm.base.LLMProvider` and implement ``classify()``.
3. Add an import and a branch in :func:`get_provider` below.
4. Add the provider name to ``Literal[...]`` in ``server/config.py``
   (``LLMConfig.provider``) so the config validator rejects unknown names.
5. Set ``LLM_PROVIDER=<name>`` (and any new credentials) in ``.env``.
6. If the provider requires an API key, add its name to ``_CLOUD_PROVIDERS``
   in ``server/core/startup.py`` so the startup validator enforces the key.
"""

from __future__ import annotations

from .base import LLMProvider

__all__ = ["LLMProvider", "get_provider"]


def get_provider(name: str, model: str, api_key: str = "") -> LLMProvider:
    """Instantiate and return the configured LLM provider.

    Args:
        name:    Value of the ``LLM_PROVIDER`` env-var (e.g. ``"ollama"``).
        model:   Model identifier passed through to the provider.
        api_key: API key for cloud providers (ignored for local ones).

    Raises:
        ValueError: if *name* does not match any registered provider.
    """
    if name == "ollama":
        from .ollama_provider import OllamaProvider  # lazy — only if ollama is installed
        return OllamaProvider(model=model)

    if name == "nvidia":
        from .nvidia_provider import NvidiaProvider
        return NvidiaProvider(model=model, api_key=api_key)

    # ── Add future providers here ──────────────────────────────────────
    # if name == "anthropic":
    #     from .anthropic_provider import AnthropicProvider
    #     return AnthropicProvider(model=model, api_key=api_key)
    # ──────────────────────────────────────────────────────────────────

    raise ValueError(
        f"Unknown LLM_PROVIDER {name!r}.  "
        f"Supported: 'ollama', 'nvidia'.  "
        f"See server/llm/__init__.py to register a new one."
    )
