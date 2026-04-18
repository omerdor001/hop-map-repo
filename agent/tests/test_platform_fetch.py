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


def _http_error_response(status_code: int) -> MagicMock:
    """Simulate requests raising HTTPError (e.g. 401, 403, 500)."""
    response = MagicMock()
    response.status_code = status_code
    error = _real_requests.exceptions.HTTPError(response=response)
    resp = MagicMock()
    resp.raise_for_status.side_effect = error
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

    def test_returns_child_id_from_server(self, tmp_path):
        """Server responds with childId — returned and cached to disk."""
        id_file = tmp_path / ".child_id"

        get_mock = MagicMock(return_value=_ok_response({"childId": "server-id-123", "childName": "Alex"}))

        with patch.object(_agent, "_CHILD_ID_FILE", id_file), \
             patch.object(_agent.config_manager, "agent_token", "valid-token"), \
             patch("requests.get", get_mock):
            child_id = _agent._register_child()

        assert child_id == "server-id-123"
        assert id_file.exists()
        assert id_file.read_text().strip() == "server-id-123"

    def test_falls_back_to_cached_id_when_server_unreachable(self, tmp_path):
        """Server is down — the locally cached ID is returned."""
        id_file = tmp_path / ".child_id"
        id_file.write_text("cached-id-456", encoding="utf-8")

        with patch.object(_agent, "_CHILD_ID_FILE", id_file), \
             patch.object(_agent.config_manager, "agent_token", "valid-token"), \
             patch("requests.get",
                   side_effect=_real_requests.exceptions.ConnectionError("refused")):
            child_id = _agent._register_child()

        assert child_id == "cached-id-456"

    def test_exits_when_no_token(self, tmp_path):
        """Empty agent_token causes sys.exit(1) before any network call."""
        id_file = tmp_path / ".child_id"

        with patch.object(_agent, "_CHILD_ID_FILE", id_file), \
             patch.object(_agent.config_manager, "agent_token", ""), \
             patch("requests.get") as get_mock:
            with pytest.raises(SystemExit) as exc_info:
                _agent._register_child()

        assert exc_info.value.code == 1
        get_mock.assert_not_called()

    def test_exits_when_server_down_and_no_cache(self, tmp_path):
        """Server unreachable and no cached ID — sys.exit(1)."""
        id_file = tmp_path / ".child_id"  # does not exist

        with patch.object(_agent, "_CHILD_ID_FILE", id_file), \
             patch.object(_agent.config_manager, "agent_token", "valid-token"), \
             patch("requests.get",
                   side_effect=_real_requests.exceptions.ConnectionError("refused")):
            with pytest.raises(SystemExit) as exc_info:
                _agent._register_child()

        assert exc_info.value.code == 1

    def test_server_id_overwrites_stale_cache(self, tmp_path):
        """Cached ID is overwritten when the server returns a different value."""
        id_file = tmp_path / ".child_id"
        id_file.write_text("old-stale-id", encoding="utf-8")

        get_mock = MagicMock(return_value=_ok_response({"childId": "fresh-id-789"}))

        with patch.object(_agent, "_CHILD_ID_FILE", id_file), \
             patch.object(_agent.config_manager, "agent_token", "valid-token"), \
             patch("requests.get", get_mock):
            child_id = _agent._register_child()

        assert child_id == "fresh-id-789"
        assert id_file.read_text().strip() == "fresh-id-789"

    @pytest.mark.parametrize("status_code", [401, 403])
    def test_exits_when_token_rejected_by_server(self, tmp_path, status_code):
        """A 401/403 from the server is fatal — stale cache must not be used."""
        id_file = tmp_path / ".child_id"
        id_file.write_text("stale-cached-id", encoding="utf-8")

        get_mock = MagicMock(return_value=_http_error_response(status_code))

        with patch.object(_agent, "_CHILD_ID_FILE", id_file), \
             patch.object(_agent.config_manager, "agent_token", "revoked-token"), \
             patch("requests.get", get_mock):
            with pytest.raises(SystemExit) as exc_info:
                _agent._register_child()

        assert exc_info.value.code == 1
