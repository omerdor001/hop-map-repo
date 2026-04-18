"""Unit tests for _classify() — the agent's HTTP call to the server classifier.

requests.post is fully mocked.  No server process is needed.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

import agent as _agent


_ClassifyResult = _agent._ClassifyResult


def _make_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.side_effect = (
        None if status_code < 400
        else requests.exceptions.HTTPError(response=resp)
    )
    return resp


class TestClassifyHappyPath:

    def test_server_returns_hop_true(self):
        payload = {"decision": "YES", "confidence": 90, "reason": "discord link", "via": "server"}
        with patch("requests.post", return_value=_make_response(payload)):
            result = _agent._classify("https://discord.gg/abc", "context", "ocr")
        assert result.is_hop is True
        assert result.confidence == 90
        assert result.reason == "discord link"
        assert result.via == "server"

    def test_server_returns_hop_false(self):
        payload = {"decision": "NO", "confidence": 5, "reason": "official game link", "via": "server"}
        with patch("requests.post", return_value=_make_response(payload)):
            result = _agent._classify("https://minecraft.net/wiki", "context", "clipboard")
        assert result.is_hop is False

    def test_decision_yes_prefix_is_hop(self):
        """Any decision starting with YES is treated as a hop."""
        payload = {"decision": "YES_STRONG", "confidence": 100, "reason": "x", "via": "server"}
        with patch("requests.post", return_value=_make_response(payload)):
            result = _agent._classify("https://t.me/bad", "ctx", "ocr")
        assert result.is_hop is True

    def test_decision_case_insensitive(self):
        payload = {"decision": "yes", "confidence": 75, "reason": "hop", "via": "server"}
        with patch("requests.post", return_value=_make_response(payload)):
            result = _agent._classify("https://discord.gg/x", "ctx", "ocr")
        assert result.is_hop is True


class TestClassifyErrorHandling:

    def test_connection_error_returns_safe_result(self):
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
            result = _agent._classify("https://evil.com/x", "ctx", "ocr")
        assert result.is_hop is False
        assert result.via == "error"

    def test_timeout_returns_safe_result(self):
        with patch("requests.post", side_effect=requests.exceptions.Timeout("timeout")):
            result = _agent._classify("https://evil.com/x", "ctx", "ocr")
        assert result.is_hop is False

    def test_http_5xx_returns_safe_result(self):
        with patch("requests.post", return_value=_make_response({}, status_code=500)):
            result = _agent._classify("https://evil.com/x", "ctx", "ocr")
        assert result.is_hop is False

    def test_http_429_returns_safe_result(self):
        with patch("requests.post", return_value=_make_response({}, status_code=429)):
            result = _agent._classify("https://evil.com/x", "ctx", "ocr")
        assert result.is_hop is False

    def test_returns_classify_result_dataclass(self):
        payload = {"decision": "NO", "confidence": 0, "reason": "clean", "via": "server"}
        with patch("requests.post", return_value=_make_response(payload)):
            result = _agent._classify("https://example.com/x", "ctx", "clipboard")
        assert isinstance(result, _ClassifyResult)

    def test_confidence_clamped_within_range(self):
        payload = {"decision": "YES", "confidence": 999, "reason": "overflow", "via": "server"}
        with patch("requests.post", return_value=_make_response(payload)):
            result = _agent._classify("https://x.com/a", "ctx", "ocr")
        assert 0 <= result.confidence <= 100
