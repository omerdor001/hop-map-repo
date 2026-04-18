"""
Integration tests for the /agent/classify endpoint (words-DB path).

Uses the mocked TestClient (app_client fixture from conftest.py) so that no
real MongoDB or Ollama instance is required.  Each word-DB test seeds the
specific blocked word it needs via POST /api/words, which also rebuilds the
in-memory Aho-Corasick filter immediately.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


# ---------------------------------------------------------------------------
# Per-test child registration (function-scoped so it survives app_client cleanup)
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
    """Verify the words-DB fast-path and LLM fallback in /agent/classify."""

    def test_clean_context_routed_to_llm(self, app_client, child_id):
        """Context without blocked words should be classified by the LLM."""
        client, _ = app_client
        res = client.post(
            "/agent/classify",
            json={
                "url":     "example.com/suspicious",
                "context": "hey bro come check this cool server",
                "childId": child_id,
                "source":  "test",
            },
        )
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

    def test_hebrew_blocked_word_in_discord_context(self, app_client, child_id):
        client, _ = app_client
        # "אחי" (bro) appears in the test context and is a Hebrew slang word
        # that would typically appear in a blocked-words list.
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
