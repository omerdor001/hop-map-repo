"""
Integration tests for the /api/words endpoints.

Requires a live server + MongoDB.  The `live_server` fixture in conftest.py
handles startup automatically.

Each test is isolated: words added during a test are cleaned up in teardown
so the shared words collection is not polluted across test runs.
"""

import pytest
import requests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_words(base_url: str) -> list[str]:
    res = requests.get(f"{base_url}/api/words", timeout=10)
    res.raise_for_status()
    return res.json()["words"]


def _add_word(base_url: str, word: str) -> dict:
    res = requests.post(f"{base_url}/api/words", json={"word": word}, timeout=10)
    res.raise_for_status()
    return res.json()


def _delete_word(base_url: str, word: str) -> dict:
    res = requests.delete(f"{base_url}/api/words/{word}", timeout=10)
    res.raise_for_status()
    return res.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWordsEndpoints:

    _test_word = "integration_test_sentinel_xyz"

    @pytest.fixture(autouse=True)
    def _cleanup(self, live_server):
        """Ensure the sentinel word is removed before and after each test."""
        requests.delete(f"{live_server}/api/words/{self._test_word}", timeout=10)
        yield
        requests.delete(f"{live_server}/api/words/{self._test_word}", timeout=10)

    def test_get_words_returns_list_and_count(self, live_server):
        res = requests.get(f"{live_server}/api/words", timeout=10)
        assert res.status_code == 200
        body = res.json()
        assert "words" in body
        assert "count" in body
        assert body["count"] == len(body["words"])

    def test_add_word_appears_in_get(self, live_server):
        _add_word(live_server, self._test_word)
        assert self._test_word in _get_words(live_server)

    def test_add_duplicate_word_is_idempotent(self, live_server):
        _add_word(live_server, self._test_word)
        before = _get_words(live_server)

        result = _add_word(live_server, self._test_word)
        after = _get_words(live_server)

        assert result["added"] is False
        assert before.count(self._test_word) == after.count(self._test_word) == 1

    def test_add_word_normalised_to_lowercase(self, live_server):
        res = requests.post(
            f"{live_server}/api/words",
            json={"word": "  UPPER_CASE_WORD_XYZ  "},
            timeout=10,
        )
        res.raise_for_status()
        normalised = "upper_case_word_xyz"
        try:
            assert normalised in _get_words(live_server)
        finally:
            requests.delete(f"{live_server}/api/words/{normalised}", timeout=10)

    def test_delete_word_removes_from_list(self, live_server):
        _add_word(live_server, self._test_word)
        assert self._test_word in _get_words(live_server)

        result = _delete_word(live_server, self._test_word)
        assert result["removed"] is True
        assert self._test_word not in _get_words(live_server)

    def test_delete_nonexistent_word_returns_removed_false(self, live_server):
        result = _delete_word(live_server, self._test_word)
        assert result["removed"] is False

    def test_reload_returns_ok_and_count(self, live_server):
        res = requests.post(f"{live_server}/api/words/reload", timeout=10)
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert isinstance(body["count"], int)
        assert body["count"] >= 0

    def test_add_empty_word_rejected(self, live_server):
        res = requests.post(f"{live_server}/api/words", json={"word": "   "}, timeout=10)
        assert res.status_code == 422

    def test_add_missing_word_field_rejected(self, live_server):
        res = requests.post(f"{live_server}/api/words", json={}, timeout=10)
        assert res.status_code == 422
