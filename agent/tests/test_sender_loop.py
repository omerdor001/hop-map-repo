"""Unit tests for _enqueue_hop(), _send_hop(), and _sender_loop().

time.sleep and time.monotonic are always mocked — no test waits for real time.
requests.post is always mocked — no real HTTP calls.
"""
from __future__ import annotations

import queue
from unittest.mock import MagicMock, call, patch

import pytest
import requests as _real_requests

import agent as _agent


def _ok_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    return resp


def _http_error(status_code: int) -> _real_requests.exceptions.HTTPError:
    response = MagicMock()
    response.status_code = status_code
    return _real_requests.exceptions.HTTPError(response=response)


def _server_error_response(status_code: int = 503) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.side_effect = _http_error(status_code)
    return resp


def _client_error_response(status_code: int = 400) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.side_effect = _http_error(status_code)
    return resp


NOW = 1_000.0  # arbitrary monotonic baseline


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def fresh_queue():
    """Swap in a clean Queue for one test; restore the module original on teardown.

    Any test that writes to _send_queue must request this fixture (directly or
    via a class-level autouse wrapper).  Without it a failing test can leave
    stale items that corrupt subsequent tests.
    """
    original = _agent._send_queue
    _agent._send_queue = queue.Queue()
    yield _agent._send_queue
    _agent._send_queue = original


# ---------------------------------------------------------------------------
# _enqueue_hop
# ---------------------------------------------------------------------------

class TestEnqueueHop:

    @pytest.fixture(autouse=True)
    def _queue_isolation(self, fresh_queue):
        pass  # fresh_queue handles swap + teardown; autouse ensures no test forgets it

    def test_puts_event_and_monotonic_timestamp(self):
        """Queue receives exactly (event, time.monotonic()) as a single item."""
        event = {"platform": "discord", "url": "https://discord.gg/abc"}

        with patch("time.monotonic", return_value=42.0):
            _agent._enqueue_hop(event)

        assert _agent._send_queue.qsize() == 1
        queued_event, queued_at = _agent._send_queue.get_nowait()
        assert queued_event == event
        assert queued_at == 42.0

    def test_monotonic_called_exactly_once_inside_enqueue(self):
        """time.monotonic() is called once, inside _enqueue_hop — not cached externally."""
        with patch("time.monotonic", return_value=99.9) as mono_mock:
            _agent._enqueue_hop({"platform": "telegram"})

        mono_mock.assert_called_once()
        _, queued_at = _agent._send_queue.get_nowait()
        assert queued_at == 99.9

    def test_event_dict_not_mutated(self):
        """_enqueue_hop never modifies the caller's event dict."""
        event = {"platform": "discord", "url": "https://discord.gg/abc"}
        snapshot = dict(event)

        with patch("time.monotonic", return_value=1.0):
            _agent._enqueue_hop(event)

        assert event == snapshot

    def test_each_call_enqueues_one_item_with_own_timestamp(self):
        """Two consecutive calls produce two items with their respective timestamps."""
        with patch("time.monotonic", side_effect=[10.0, 20.0]):
            _agent._enqueue_hop({"n": 1})
            _agent._enqueue_hop({"n": 2})

        assert _agent._send_queue.qsize() == 2
        _, t1 = _agent._send_queue.get_nowait()
        _, t2 = _agent._send_queue.get_nowait()
        assert t1 == 10.0
        assert t2 == 20.0


class TestSendHop:

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_successful_send_on_first_attempt(self):
        with patch("requests.post", return_value=_ok_response()) as post_mock, \
             patch("time.sleep") as sleep_mock, \
             patch("time.monotonic", return_value=NOW):
            _agent._send_hop({"type": "hop"}, NOW)

        post_mock.assert_called_once()
        sleep_mock.assert_not_called()

    def test_post_called_with_correct_url_and_auth(self):
        """The URL includes child_id and the Bearer token from config."""
        event = {"platform": "discord"}

        with patch.object(_agent.config_manager, "backend_url", "http://server:8000"), \
             patch.object(_agent, "_child_id", "child-42"), \
             patch.object(_agent.config_manager, "agent_token", "tok-abc"), \
             patch("requests.post", return_value=_ok_response()) as post_mock, \
             patch("time.sleep"), \
             patch("time.monotonic", return_value=NOW):
            _agent._send_hop(event, NOW)

        post_mock.assert_called_once_with(
            "http://server:8000/agent/hop/child-42",
            json=event,
            headers={"Authorization": "Bearer tok-abc"},
            timeout=_agent._HTTP_TIMEOUT_S,
        )

    # ------------------------------------------------------------------
    # 4xx — drop immediately, no retry
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 429])
    def test_4xx_any_code_dropped_immediately(self, status_code):
        with patch("requests.post", return_value=_client_error_response(status_code)) as post_mock, \
             patch("time.sleep") as sleep_mock, \
             patch("time.monotonic", return_value=NOW):
            _agent._send_hop({"type": "hop"}, NOW)

        post_mock.assert_called_once()
        sleep_mock.assert_not_called()

    # ------------------------------------------------------------------
    # 5xx — retry then succeed / retry then exhaust
    # ------------------------------------------------------------------

    def test_5xx_retried_then_succeeds(self):
        post_mock = MagicMock(side_effect=[_server_error_response(503), _ok_response()])

        with patch("requests.post", post_mock), \
             patch("time.sleep") as sleep_mock, \
             patch("time.monotonic", return_value=NOW):
            _agent._send_hop({"type": "hop"}, NOW)

        assert post_mock.call_count == 2
        sleep_mock.assert_called_once_with(5)

    def test_all_5xx_retries_exhausted_drops_event(self):
        post_mock = MagicMock(return_value=_server_error_response(503))

        with patch("requests.post", post_mock), \
             patch("time.sleep") as sleep_mock, \
             patch("time.monotonic", return_value=NOW):
            _agent._send_hop({"type": "hop"}, NOW)

        assert post_mock.call_count == 5
        assert sleep_mock.call_count == 4
        assert sleep_mock.call_args_list == [call(5), call(10), call(20), call(30)]

    # ------------------------------------------------------------------
    # Network errors — retry then succeed / retry then exhaust
    # ------------------------------------------------------------------

    def test_connection_error_retried_then_succeeds(self):
        conn_err = _real_requests.exceptions.ConnectionError("refused")
        post_mock = MagicMock(side_effect=[conn_err, _ok_response()])

        with patch("requests.post", post_mock), \
             patch("time.sleep") as sleep_mock, \
             patch("time.monotonic", return_value=NOW):
            _agent._send_hop({"type": "hop"}, NOW)

        assert post_mock.call_count == 2
        sleep_mock.assert_called_once_with(5)

    def test_timeout_retried_then_succeeds(self):
        """Timeout is a RequestException (not HTTPError) — must also trigger retry."""
        timeout_err = _real_requests.exceptions.Timeout("timed out")
        post_mock = MagicMock(side_effect=[timeout_err, _ok_response()])

        with patch("requests.post", post_mock), \
             patch("time.sleep") as sleep_mock, \
             patch("time.monotonic", return_value=NOW):
            _agent._send_hop({"type": "hop"}, NOW)

        assert post_mock.call_count == 2
        sleep_mock.assert_called_once_with(5)

    def test_all_network_retries_exhausted_drops_event(self):
        conn_err = _real_requests.exceptions.ConnectionError("refused")
        post_mock = MagicMock(side_effect=conn_err)

        with patch("requests.post", post_mock), \
             patch("time.sleep") as sleep_mock, \
             patch("time.monotonic", return_value=NOW):
            _agent._send_hop({"type": "hop"}, NOW)

        assert post_mock.call_count == 5  # 1 immediate + 4 retries
        assert sleep_mock.call_count == 4
        assert sleep_mock.call_args_list == [call(5), call(10), call(20), call(30)]

    # ------------------------------------------------------------------
    # HTTPError with no response object
    # ------------------------------------------------------------------

    def test_http_error_without_response_retried(self):
        """HTTPError with exc.response=None cannot be classified as 4xx — must retry."""
        no_resp_err = _real_requests.exceptions.HTTPError(response=None)
        post_mock = MagicMock(side_effect=[no_resp_err, _ok_response()])

        with patch("requests.post", post_mock), \
             patch("time.sleep") as sleep_mock, \
             patch("time.monotonic", return_value=NOW):
            _agent._send_hop({"type": "hop"}, NOW)

        assert post_mock.call_count == 2
        sleep_mock.assert_called_once_with(5)

    # ------------------------------------------------------------------
    # TTL / expiry
    # ------------------------------------------------------------------

    def test_event_expired_before_first_attempt(self):
        stale_enqueued_at = NOW - (_agent._HOP_MAX_AGE_S + 1)

        with patch("requests.post") as post_mock, \
             patch("time.sleep"), \
             patch("time.monotonic", return_value=NOW):
            _agent._send_hop({"type": "hop"}, stale_enqueued_at)

        post_mock.assert_not_called()

    def test_event_at_exact_ttl_boundary_not_dropped(self):
        """Age == _HOP_MAX_AGE_S exactly is NOT expired (condition is strictly >)."""
        enqueued_at = NOW - _agent._HOP_MAX_AGE_S  # diff == 300.0, not > 300.0

        with patch("requests.post", return_value=_ok_response()) as post_mock, \
             patch("time.sleep"), \
             patch("time.monotonic", return_value=NOW):
            _agent._send_hop({"type": "hop"}, enqueued_at)

        post_mock.assert_called_once()

    def test_event_expires_during_retry(self):
        # TTL check before attempt 1: NOW → within limit → post runs → ConnectionError.
        # TTL check before attempt 2: expired → return without second post.
        monotonic_values = [NOW, NOW + _agent._HOP_MAX_AGE_S + 1]
        conn_err = _real_requests.exceptions.ConnectionError("refused")

        with patch("requests.post", side_effect=[conn_err]) as post_mock, \
             patch("time.sleep"), \
             patch("time.monotonic", side_effect=monotonic_values):
            _agent._send_hop({"type": "hop"}, NOW)

        post_mock.assert_called_once()  # first attempt ran; second was blocked by TTL


class TestSenderLoop:

    @pytest.fixture(autouse=True)
    def _queue_isolation(self, fresh_queue):
        pass  # fresh_queue handles swap + teardown; autouse ensures no test forgets it

    def test_shutdown_sentinel_stops_loop(self):
        """None in the queue causes _sender_loop to return cleanly."""
        _agent._send_queue.put(None)

        with patch.object(_agent, "_send_hop") as send_mock:
            _agent._sender_loop()

        send_mock.assert_not_called()

    def test_delivers_event_then_stops_on_sentinel(self):
        """One real event followed by None: _send_hop called once with correct args."""
        event = {"type": "hop", "platform": "discord"}
        enqueued_at = 42.0
        _agent._send_queue.put((event, enqueued_at))
        _agent._send_queue.put(None)

        with patch.object(_agent, "_send_hop") as send_mock:
            _agent._sender_loop()

        send_mock.assert_called_once_with(event, enqueued_at)

    def test_delivers_multiple_events_then_stops_on_sentinel(self):
        """Multiple events are each forwarded to _send_hop in order."""
        events = [
            ({"platform": "discord"}, 10.0),
            ({"platform": "telegram"}, 20.0),
        ]
        for event, ts in events:
            _agent._send_queue.put((event, ts))
        _agent._send_queue.put(None)

        with patch.object(_agent, "_send_hop") as send_mock:
            _agent._sender_loop()

        assert send_mock.call_count == 2
        send_mock.assert_any_call({"platform": "discord"}, 10.0)
        send_mock.assert_any_call({"platform": "telegram"}, 20.0)
