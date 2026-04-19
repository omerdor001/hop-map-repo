"""
Integration tests for the /agent/classify endpoint.

Uses the mocked TestClient (app_client fixture from conftest.py) so that no
real MongoDB or Ollama instance is required.  All tests that exercise the LLM
path patch classify.service.run_classify directly — the server lifespan
replaces the mock LLM with a real OllamaProvider when TestClient starts, so
patching at the service boundary is the only robust seam.

Each word-DB test seeds the specific blocked word it needs via POST /api/words,
which also rebuilds the in-memory Aho-Corasick filter immediately.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from classify.exceptions import (
    LLMInferenceError,
    LLMResponseParseError,
    LLMTimeoutError,
    LLMUnavailableError,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Full import path used by both test classes when patching the LLM service call.
_RUN_CLASSIFY = "classify.service.run_classify"

# Plain gameplay context — no platform names, no lure phrases, no blocked words.
_CLEAN_PAYLOAD = {
    "url":     "example.com",
    "context": "great game today nice moves",
    "source":  "test",
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def child_id(app_client):
    """Register a fresh child for each test (after app_client resets state)."""
    client, _ = app_client
    res = client.post("/api/children", json={})
    res.raise_for_status()
    return res.json()["childId"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClassifyEndpointWordsDB:
    """Verify the words-DB fast-path and LLM routing in /agent/classify."""

    def test_clean_context_routed_to_llm(self, app_client, child_id):
        """Context with no blocked words bypasses the word filter and hits the LLM path."""
        client, _ = app_client
        mock_result = {"decision": "NO", "confidence": 5, "reason": "clean"}
        with patch(_RUN_CLASSIFY, new=AsyncMock(return_value=mock_result)):
            res = client.post("/agent/classify", json={**_CLEAN_PAYLOAD, "childId": child_id})
        res.raise_for_status()
        assert res.json()["via"] == "server"

    def test_blocked_word_hack_caught_by_words_db(self, app_client, child_id):
        """The word 'hack' must be caught by the words DB, not the LLM."""
        client, _ = app_client
        # Seed the blocked word so the in-memory filter catches it.
        client.post("/api/words", json={"word": "hack"})
        res = client.post(
            "/agent/classify",
            json={
                "url":     "example.com/page",
                "context": "click here to hack your friends account",
                "childId": child_id,
                "source":  "test",
            },
        )
        res.raise_for_status()
        data = res.json()
        assert data["via"]        == "word_db"
        assert data["confidence"] == 100
        assert "hack" in data["reason"]
        assert data["decision"]   == "YES"

    def test_18plus_caught_by_words_db(self, app_client, child_id):
        """Special-character phrases like '18+' are matched correctly by the filter."""
        client, _ = app_client
        client.post("/api/words", json={"word": "18+"})
        res = client.post(
            "/agent/classify",
            json={
                "url":     "example.com/page",
                "context": "check out this 18+ content",
                "childId": child_id,
                "source":  "test",
            },
        )
        res.raise_for_status()
        data = res.json()
        assert data["via"]      == "word_db"
        assert data["decision"] == "YES"

    def test_clean_context_via_server(self, app_client, child_id):
        """LLM result is correctly passed through to the response (decision, confidence, reason)."""
        client, _ = app_client
        mock_result = {"decision": "YES", "confidence": 90, "reason": "discord link"}
        with patch(_RUN_CLASSIFY, new=AsyncMock(return_value=mock_result)):
            res = client.post(
                "/agent/classify",
                json={
                    "url":     "discord.gg/abc",
                    "context": "join my discord",
                    "childId": child_id,
                    "source":  "test",
                },
            )
        res.raise_for_status()
        data = res.json()
        assert data["via"]        == "server"
        assert data["decision"]   == "YES"
        assert data["confidence"] == 90
        assert data["reason"]     == "discord link"

    def test_hebrew_blocked_word_in_discord_context(self, app_client, child_id):
        """Unicode (Hebrew) blocked words are matched correctly by the Aho-Corasick filter."""
        client, _ = app_client
        client.post("/api/words", json={"word": "אחי"})
        res = client.post(
            "/agent/classify",
            json={
                "url":     "discord.gg/abc123",
                "context": "בוא לדיסקורד שלי אחי",
                "childId": child_id,
                "source":  "test",
            },
        )
        res.raise_for_status()
        data = res.json()
        assert data["via"] == "word_db"


class TestClassifyEndpointLLMErrors:
    """Verify graceful safe-NO fallback for each LLM failure mode.

    We patch classify.service.run_classify directly rather than the mock LLM
    because the server lifespan re-initialises _llm with a real OllamaProvider
    when TestClient starts up, so mock-LLM side_effects would be silently lost.
    Patching at the service boundary is robust to the initialisation order.

    Each test asserts:
    - HTTP 200 — never leaks a 500 to the agent
    - decision="NO" — fail-safe behaviour
    - a stable machine-readable reason code for monitoring/alerting
    """

    @pytest.mark.parametrize(
        "exc, expected_reason",
        [
            (LLMUnavailableError("daemon down"), "llm_unavailable"),
            (LLMTimeoutError("timed out after 30s"), "llm_timeout"),
            (LLMInferenceError("Ollama 500"), "llm_inference_error"),
            (
                LLMResponseParseError(
                    "not valid json",
                    json.JSONDecodeError("Expecting value", "not valid json", 0),
                ),
                "llm_parse_error",
            ),
        ],
        ids=["unavailable", "timeout", "inference_error", "parse_error"],
    )
    def test_llm_error_returns_safe_no(self, app_client, child_id, exc, expected_reason):
        """Each LLM failure mode returns decision=NO with the correct reason code."""
        client, _ = app_client
        with patch(_RUN_CLASSIFY, new=AsyncMock(side_effect=exc)):
            res = client.post("/agent/classify", json={**_CLEAN_PAYLOAD, "childId": child_id})
        res.raise_for_status()
        data = res.json()
        assert data["decision"] == "NO"
        assert data["reason"]   == expected_reason

    def test_llm_error_never_leaks_500(self, app_client, child_id):
        """Any LLM failure must produce HTTP 200 — the agent must never see a 500."""
        client, _ = app_client
        with patch(_RUN_CLASSIFY, new=AsyncMock(side_effect=LLMUnavailableError("daemon down"))):
            res = client.post("/agent/classify", json={**_CLEAN_PAYLOAD, "childId": child_id})
        assert res.status_code == 200
