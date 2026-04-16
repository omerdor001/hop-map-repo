"""Ollama LLM provider — local inference via the Ollama desktop client.

Configured by:
    OLLAMA_MODEL=qwen2.5:7b   (or any model you have pulled locally)

The Ollama daemon must be running on the server machine.
"""

from __future__ import annotations

import ollama

from .base import LLMProvider


class OllamaProvider(LLMProvider):
    """Calls a locally running Ollama model for classification.

    ``model`` is the Ollama model tag, e.g. ``"qwen2.5:7b"``.
    Controlled by the ``OLLAMA_MODEL`` env-var in ``.env``.
    """

    def __init__(self, model: str) -> None:
        self.model = model

    def classify(self, context: str, system_prompt: str) -> dict:
        response = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": context},
            ],
            options={"temperature": 0},
        )
        raw = response["message"]["content"].strip()
        return self._parse_response(raw)
