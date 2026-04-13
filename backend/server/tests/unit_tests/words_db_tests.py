"""
Words DB tests - run with: pytest words_db_tests.py -v
"""

import pytest
import requests

BASE = "http://localhost:8000"


@pytest.fixture(scope="module")
def child_id():
    """Register a child once for all tests."""
    res = requests.post(f"{BASE}/api/children", json={})
    return res.json()["childId"]


class TestWordsDB:
    """Tests for the words database filtering."""

    def test_via_llm_no_blocked_word(self, child_id):
        """Context without blocked words should go through LLM."""
        res = requests.post(
            f"{BASE}/agent/classify",
            json={
                "url": "example.com/suspicious",
                "context": "hey bro come check this cool server",
                "childId": child_id,
                "source": "test",
            },
            timeout=30,
        )
        result = res.json()
        assert result["via"] == "server"

    def test_via_words_db_word_hack(self, child_id):
        """Blocked word 'hack' should be caught by words DB."""
        res = requests.post(
            f"{BASE}/agent/classify",
            json={
                "url": "example.com/page",
                "context": "click here to hack your friends account",
                "childId": child_id,
                "source": "test",
            },
        )
        result = res.json()
        assert result["via"] == "word_db"
        assert result["confidence"] == 100
        assert "hack" in result["reason"]
        assert result["decision"] == "YES"

    @pytest.mark.xfail(reason="'+' character not matched by \\w+ regex")
    def test_via_words_db_18plus(self, child_id):
        """Blocked word '18+' should be caught by words DB."""
        res = requests.post(
            f"{BASE}/agent/classify",
            json={
                "url": "example.com/page",
                "context": "check out this 18+ content",
                "childId": child_id,
                "source": "test",
            },
        )
        result = res.json()
        assert result["via"] == "word_db"
        assert result["confidence"] == 100
        assert "18+" in result["reason"]
        assert result["decision"] == "YES"

    @pytest.mark.xfail(reason="Hebrew unicode not matched by \\w+ regex")
    def test_via_word_db_hebrew_discord(self, child_id):
        """Hebrew 'discord' should be caught by words DB."""
        res = requests.post(
            f"{BASE}/agent/classify",
            json={
                "url": "example.com/page",
                "context": "בוא לדיסקורד שלי זה מגניב",
                "childId": child_id,
                "source": "test",
            },
        )
        result = res.json()
        assert result["via"] == "word_db"
        assert result["confidence"] == 100
        assert result["decision"] == "YES"

