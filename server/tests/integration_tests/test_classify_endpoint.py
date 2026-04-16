"""
Integration tests for the /agent/classify endpoint (words-DB path).

Requires a live server + MongoDB.  The `live_server` fixture in conftest.py
handles startup automatically — if the dev server is already running on
localhost:8000 it is reused; otherwise a new instance is started on a free port.
"""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


# ---------------------------------------------------------------------------
# Module-scoped child registration
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def child_id(live_server):
    """Register a child once for all tests in this module."""
    res = requests.post(f"{live_server}/api/children", json={})
    res.raise_for_status()
    return res.json()["childId"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestClassifyEndpointWordsDB:
    """Verify the words-DB fast-path and LLM fallback in /agent/classify."""

    def test_clean_context_routed_to_llm(self, live_server, child_id):
        """Context without blocked words should be classified by the LLM."""
        res = requests.post(
            f"{live_server}/agent/classify",
            json={
                "url":     "example.com/suspicious",
                "context": "hey bro come check this cool server",
                "childId": child_id,
                "source":  "test",
            },
            timeout=30,
        )
        res.raise_for_status()
        assert res.json()["via"] == "server"

    def test_blocked_word_hack_caught_by_words_db(self, live_server, child_id):
        """The word 'hack' must be caught by the words DB, not the LLM."""
        res = requests.post(
            f"{live_server}/agent/classify",
            json={
                "url":     "example.com/page",
                "context": "click here to hack your friends account",
                "childId": child_id,
                "source":  "test",
            },
            timeout=30,
        )
        res.raise_for_status()
        data = res.json()
        assert data["via"]        == "word_db"
        assert data["confidence"] == 100
        assert "hack" in data["reason"]
        assert data["decision"]   == "YES"


    def test_18plus_caught_by_words_db(self, live_server, child_id):
        res = requests.post(
            f"{live_server}/agent/classify",
            json={
                "url":     "example.com/page",
                "context": "check out this 18+ content",
                "childId": child_id,
                "source":  "test",
            },
            timeout=30,
        )
        res.raise_for_status()
        data = res.json()
        assert data["via"] == "word_db"
        assert data["decision"] == "YES"


    def test_hebrew_blocked_word_in_discord_context(self, live_server, child_id):
        res = requests.post(
            f"{live_server}/agent/classify",
            json={
                "url":     "discord.gg/abc123",
                "context": "בוא לדיסקורד שלי אחי",
                "childId": child_id,
                "source":  "test",
            },
            timeout=30,
        )
        res.raise_for_status()
        data = res.json()
        assert data["via"] == "word_db"
