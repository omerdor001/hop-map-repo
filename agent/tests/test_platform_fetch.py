"""Unit tests for _fetch_platform_db() and _register_child().

requests is patched to avoid real HTTP calls.  File I/O for the child-ID
persistence uses pytest's tmp_path fixture.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests as _real_requests

import agent as _agent


def _ok_response(json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _error_response(status_code: int = 500) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status.side_effect = _real_requests.exceptions.HTTPError()
    return resp


# ---------------------------------------------------------------------------
# _fetch_platform_db
# ---------------------------------------------------------------------------

class TestFetchPlatformDb:

    def setup_method(self):
        """Reset runtime globals before each test."""
        _agent._PLATFORM_APP_MAP  = {}
        _agent._BROWSER_PROCESSES = frozenset()
        _agent._TRANSIT_PROCESSES = frozenset()

    def test_populates_platform_map_from_server(self):
        server_data = {
            "platforms": {"discord": ["discord.exe"], "telegram": ["telegram.exe"]},
            "browsers":  ["chrome.exe"],
            "transit":   ["explorer.exe"],
        }
        with patch("requests.get", return_value=_ok_response(server_data)):
            _agent._fetch_platform_db()

        assert "discord" in _agent._PLATFORM_APP_MAP
        assert "discord.exe" in _agent._PLATFORM_APP_MAP["discord"]

    def test_populates_browsers_from_server(self):
        server_data = {
            "platforms": {"discord": ["discord.exe"]},
            "browsers":  ["chrome.exe", "firefox.exe"],
            "transit":   [],
        }
        with patch("requests.get", return_value=_ok_response(server_data)):
            _agent._fetch_platform_db()

        assert "chrome.exe" in _agent._BROWSER_PROCESSES
        assert "firefox.exe" in _agent._BROWSER_PROCESSES

    def test_populates_transit_from_server(self):
        server_data = {
            "platforms": {"discord": ["discord.exe"]},
            "browsers":  [],
            "transit":   ["explorer.exe"],
        }
        with patch("requests.get", return_value=_ok_response(server_data)):
            _agent._fetch_platform_db()

        assert "explorer.exe" in _agent._TRANSIT_PROCESSES

    def test_falls_back_to_defaults_on_connection_error(self):
        with patch("requests.get",
                   side_effect=_real_requests.exceptions.ConnectionError("refused")):
            _agent._fetch_platform_db()

        # Defaults include "discord.exe" for discord platform.
        assert "discord" in _agent._PLATFORM_APP_MAP

    def test_falls_back_to_defaults_on_http_error(self):
        with patch("requests.get", return_value=_error_response(503)):
            _agent._fetch_platform_db()

        assert "discord" in _agent._PLATFORM_APP_MAP

    def test_falls_back_when_server_returns_empty_platform_map(self):
        """An empty platform map from the server triggers the fallback."""
        server_data = {"platforms": {}, "browsers": [], "transit": []}
        with patch("requests.get", return_value=_ok_response(server_data)):
            _agent._fetch_platform_db()

        # Defaults must be active.
        assert len(_agent._PLATFORM_APP_MAP) > 0

    def test_falls_back_on_invalid_json_structure(self):
        """A response missing the 'platforms' key triggers the ValueError fallback."""
        # Return a valid dict but missing the 'platforms' key — raw_map will be {}
        # which raises ValueError("Server returned empty platform map.") → caught → fallback.
        server_data = {"wrong_key": "value"}
        with patch("requests.get", return_value=_ok_response(server_data)):
            _agent._fetch_platform_db()

        assert len(_agent._PLATFORM_APP_MAP) > 0


# ---------------------------------------------------------------------------
# _register_child
# ---------------------------------------------------------------------------

class TestRegisterChild:

    def test_reads_persisted_id_without_posting(self, tmp_path):
        id_file = tmp_path / ".child_id"
        id_file.write_text("stored-id-123", encoding="utf-8")

        post_mock = MagicMock(return_value=_ok_response({"childId": "stored-id-123"}))

        with patch.object(_agent, "_CHILD_ID_FILE", id_file), \
             patch("requests.get", MagicMock()), \
             patch("requests.post", post_mock):
            child_id = _agent._register_child()

        assert child_id == "stored-id-123"

    def test_registers_fresh_when_no_id_file(self, tmp_path):
        id_file = tmp_path / ".child_id"
        # File does not exist.

        post_mock = MagicMock(return_value=_ok_response({"childId": "new-id-456"}))

        with patch.object(_agent, "_CHILD_ID_FILE", id_file), \
             patch("requests.post", post_mock):
            child_id = _agent._register_child()

        assert child_id == "new-id-456"
        # ID must be persisted to disk.
        assert id_file.exists()
        assert id_file.read_text().strip() == "new-id-456"

    def test_returns_fallback_id_when_server_unreachable(self, tmp_path):
        id_file = tmp_path / ".child_id"

        with patch.object(_agent, "_CHILD_ID_FILE", id_file), \
             patch("requests.post",
                   side_effect=_real_requests.exceptions.ConnectionError("refused")):
            child_id = _agent._register_child()

        assert child_id == "child-unknown"

    def test_persists_id_to_file_after_registration(self, tmp_path):
        id_file = tmp_path / ".child_id"

        post_mock = MagicMock(return_value=_ok_response({"childId": "persisted-789"}))

        with patch.object(_agent, "_CHILD_ID_FILE", id_file), \
             patch("requests.post", post_mock):
            _agent._register_child()

        assert id_file.read_text().strip() == "persisted-789"
