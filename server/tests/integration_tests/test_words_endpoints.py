"""Integration tests for the /api/words endpoints.

Uses the mocked TestClient (app_client fixture from conftest.py) so that no
real MongoDB or Ollama instance is required.
"""
from __future__ import annotations

import pytest


class TestWordsEndpoints:

    _test_word = "integration_test_sentinel_xyz"

    @pytest.fixture(autouse=True)
    def _cleanup(self, app_client):
        client, _ = app_client
        client.delete(f"/api/words/{self._test_word}")
        yield
        client.delete(f"/api/words/{self._test_word}")

    def test_get_words_returns_list_and_count(self, app_client):
        client, _ = app_client
        res = client.get("/api/words")
        assert res.status_code == 200
        body = res.json()
        assert "words" in body
        assert "count" in body
        assert body["count"] == len(body["words"])

    def test_add_word_appears_in_get(self, app_client):
        client, _ = app_client
        client.post("/api/words", json={"word": self._test_word})
        words = client.get("/api/words").json()["words"]
        assert self._test_word in words

    def test_add_duplicate_word_is_idempotent(self, app_client):
        client, _ = app_client
        client.post("/api/words", json={"word": self._test_word})
        before = client.get("/api/words").json()["words"]

        result = client.post("/api/words", json={"word": self._test_word}).json()
        after = client.get("/api/words").json()["words"]

        assert result["added"] is False
        assert before.count(self._test_word) == after.count(self._test_word) == 1

    def test_add_word_normalised_to_lowercase(self, app_client):
        client, _ = app_client
        client.post("/api/words", json={"word": "  UPPER_CASE_WORD_XYZ  "})
        normalised = "upper_case_word_xyz"
        try:
            assert normalised in client.get("/api/words").json()["words"]
        finally:
            client.delete(f"/api/words/{normalised}")

    def test_delete_word_removes_from_list(self, app_client):
        client, _ = app_client
        client.post("/api/words", json={"word": self._test_word})
        assert self._test_word in client.get("/api/words").json()["words"]

        result = client.delete(f"/api/words/{self._test_word}").json()
        assert result["removed"] is True
        assert self._test_word not in client.get("/api/words").json()["words"]

    def test_delete_nonexistent_word_returns_removed_false(self, app_client):
        client, _ = app_client
        result = client.delete(f"/api/words/{self._test_word}").json()
        assert result["removed"] is False

    def test_reload_returns_ok_and_count(self, app_client):
        client, _ = app_client
        res = client.post("/api/words/reload")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert isinstance(body["count"], int)
        assert body["count"] >= 0

    def test_add_empty_word_rejected(self, app_client):
        client, _ = app_client
        res = client.post("/api/words", json={"word": "   "})
        assert res.status_code == 422

    def test_add_missing_word_field_rejected(self, app_client):
        client, _ = app_client
        res = client.post("/api/words", json={})
        assert res.status_code == 422
