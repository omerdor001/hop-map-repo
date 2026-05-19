"""Unit tests for the hop-confirmation pipeline.

Covers _try_late_confirm, _decide_and_send, and _drain_and_confirm.

All external dependencies (Win32 APIs, HTTP classify call, platform globals)
are mocked so these tests run on any platform without a server.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest

import agent as _agent


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_switch(proc: str, at: float, hwnd: int = 1001, title: str = "") -> dict:
    return {"proc": proc, "title": title, "hwnd": hwnd, "at": at}


def _make_pending(url: str = "https://discord.gg/abc", game: str = "roblox.exe") -> _agent._PendingHop:
    return {
        "from": game,
        "to": url,
        "fromTitle": "Roblox",
        "toTitle": f"[link] {url}",
        "context": "join us!",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "detection": "confirmed_hop",
        "classifyConfidence": 90,
        "classifyReason": "discord invite",
        "classifySource": "server",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_hop_state():
    """Isolate each test: clear mutable globals before and after."""
    _agent._pending_hop_attempts.clear()
    _agent._last_non_game_switch = None
    yield
    _agent._pending_hop_attempts.clear()
    _agent._last_non_game_switch = None


# ---------------------------------------------------------------------------
# _try_late_confirm — Check 1 (recorded switch)
# ---------------------------------------------------------------------------

class TestTryLateConfirmCheck1:
    """Check 1 trusts _last_non_game_switch only when the switch postdates detection."""

    def test_switch_after_detection_confirms(self):
        now = time.monotonic()
        _agent._last_non_game_switch = _make_switch("discord.exe", at=now - 2.0, hwnd=1001, title="Discord")
        detected_at = now - 5.0  # URL was seen 5 s ago; switch happened 2 s ago → after detection

        with patch.object(_agent, "_drain_and_confirm") as mock_drain, \
             patch.object(_agent, "_is_hop_destination", return_value=True):
            _agent._try_late_confirm("roblox.exe", detected_at)

        mock_drain.assert_called_once_with("discord.exe", "Discord", 1001)

    def test_switch_before_detection_skips_check1(self):
        """The fix: a stale switch that predates detection must not fire."""
        now = time.monotonic()
        _agent._last_non_game_switch = _make_switch("discord.exe", at=now - 10.0)
        detected_at = now - 5.0  # URL detected after the switch → switch is stale

        with patch.object(_agent, "_drain_and_confirm") as mock_drain, \
             patch.object(_agent, "_is_game", return_value=True), \
             patch.object(_agent, "_resolve_window", return_value=("roblox.exe", "Roblox")), \
             patch.object(_agent.win32gui, "GetForegroundWindow", return_value=0):
            _agent._try_late_confirm("roblox.exe", detected_at)

        mock_drain.assert_not_called()

    def test_switch_exceeds_max_age_skips_check1(self):
        now = time.monotonic()
        _agent._last_non_game_switch = _make_switch("discord.exe", at=now - 61.0)
        detected_at = now - 62.0  # switch is after detection but older than 60 s limit

        with patch.object(_agent, "_drain_and_confirm") as mock_drain, \
             patch.object(_agent, "_is_game", return_value=True), \
             patch.object(_agent, "_resolve_window", return_value=("roblox.exe", "Roblox")), \
             patch.object(_agent.win32gui, "GetForegroundWindow", return_value=0):
            _agent._try_late_confirm("roblox.exe", detected_at)

        mock_drain.assert_not_called()

    def test_switch_to_non_hop_destination_skips_check1(self):
        now = time.monotonic()
        _agent._last_non_game_switch = _make_switch("notepad.exe", at=now - 2.0)
        detected_at = now - 5.0

        with patch.object(_agent, "_drain_and_confirm") as mock_drain, \
             patch.object(_agent, "_is_hop_destination", return_value=False), \
             patch.object(_agent, "_is_game", return_value=True), \
             patch.object(_agent, "_resolve_window", return_value=("roblox.exe", "Roblox")), \
             patch.object(_agent.win32gui, "GetForegroundWindow", return_value=0):
            _agent._try_late_confirm("roblox.exe", detected_at)

        mock_drain.assert_not_called()

    def test_no_recorded_switch_skips_check1(self):
        _agent._last_non_game_switch = None
        detected_at = time.monotonic() - 5.0

        with patch.object(_agent, "_drain_and_confirm") as mock_drain, \
             patch.object(_agent, "_is_game", return_value=True), \
             patch.object(_agent.win32gui, "GetForegroundWindow", return_value=0), \
             patch.object(_agent, "_resolve_window", return_value=("roblox.exe", "Roblox")):
            _agent._try_late_confirm("roblox.exe", detected_at)

        mock_drain.assert_not_called()

    def test_switch_at_exact_detection_boundary_confirms(self):
        """last["at"] == detected_at satisfies >= so Check 1 must fire."""
        now = time.monotonic()
        _agent._last_non_game_switch = _make_switch("discord.exe", at=now, hwnd=1001, title="Discord")
        detected_at = now  # switch and detection at the same instant

        with patch.object(_agent, "_drain_and_confirm") as mock_drain, \
             patch.object(_agent, "_is_hop_destination", return_value=True):
            _agent._try_late_confirm("roblox.exe", detected_at)

        mock_drain.assert_called_once_with("discord.exe", "Discord", 1001)


# ---------------------------------------------------------------------------
# _try_late_confirm — Check 2 (current foreground fallback)
# ---------------------------------------------------------------------------

class TestTryLateConfirmCheck2:
    """Check 2 fires when Check 1 finds nothing and the current app is a hop destination."""

    def test_currently_on_hop_destination_confirms(self):
        _agent._last_non_game_switch = None
        detected_at = time.monotonic() - 5.0

        with patch.object(_agent, "_drain_and_confirm") as mock_drain, \
             patch.object(_agent, "_is_hop_destination", return_value=True), \
             patch.object(_agent, "_is_game", return_value=False), \
             patch.object(_agent.win32gui, "GetForegroundWindow", return_value=2001), \
             patch.object(_agent, "_resolve_window", return_value=("discord.exe", "Discord")):
            _agent._try_late_confirm("roblox.exe", detected_at)

        mock_drain.assert_called_once_with("discord.exe", "Discord", 2001)

    def test_currently_in_game_no_confirm(self):
        _agent._last_non_game_switch = None
        detected_at = time.monotonic() - 5.0

        with patch.object(_agent, "_drain_and_confirm") as mock_drain, \
             patch.object(_agent, "_is_game", return_value=True), \
             patch.object(_agent.win32gui, "GetForegroundWindow", return_value=2001), \
             patch.object(_agent, "_resolve_window", return_value=("minecraft.exe", "Minecraft")):
            _agent._try_late_confirm("roblox.exe", detected_at)

        mock_drain.assert_not_called()

    def test_currently_in_transit_process_no_confirm(self):
        _agent._last_non_game_switch = None
        detected_at = time.monotonic() - 5.0

        with patch.object(_agent, "_drain_and_confirm") as mock_drain, \
             patch.object(_agent, "_is_game", return_value=False), \
             patch.object(_agent, "_transit_processes", frozenset({"explorer.exe"})), \
             patch.object(_agent.win32gui, "GetForegroundWindow", return_value=2001), \
             patch.object(_agent, "_resolve_window", return_value=("explorer.exe", "File Explorer")):
            _agent._try_late_confirm("roblox.exe", detected_at)

        mock_drain.assert_not_called()

    def test_currently_on_same_game_proc_no_confirm(self):
        _agent._last_non_game_switch = None
        detected_at = time.monotonic() - 5.0

        with patch.object(_agent, "_drain_and_confirm") as mock_drain, \
             patch.object(_agent, "_is_game", return_value=False), \
             patch.object(_agent.win32gui, "GetForegroundWindow", return_value=2001), \
             patch.object(_agent, "_resolve_window", return_value=("roblox.exe", "Roblox")):
            _agent._try_late_confirm("roblox.exe", detected_at)

        mock_drain.assert_not_called()

    def test_currently_on_non_hop_destination_no_confirm(self):
        _agent._last_non_game_switch = None
        detected_at = time.monotonic() - 5.0

        with patch.object(_agent, "_drain_and_confirm") as mock_drain, \
             patch.object(_agent, "_is_game", return_value=False), \
             patch.object(_agent, "_is_hop_destination", return_value=False), \
             patch.object(_agent.win32gui, "GetForegroundWindow", return_value=2001), \
             patch.object(_agent, "_resolve_window", return_value=("notepad.exe", "Notepad")):
            _agent._try_late_confirm("roblox.exe", detected_at)

        mock_drain.assert_not_called()


# ---------------------------------------------------------------------------
# _decide_and_send
# ---------------------------------------------------------------------------

class TestDecideAndSend:

    def test_safe_classification_does_not_park_pending(self):
        safe = _agent._ClassifyResult(is_hop=False, confidence=5, reason="clean", via="server")

        with patch.object(_agent, "_classify", return_value=safe), \
             patch.object(_agent, "_try_late_confirm") as mock_late:
            _agent._decide_and_send(
                "https://example.com/x", "ctx", "roblox.exe", "Roblox", "ocr",
                time.monotonic(),
            )

        assert "https://example.com/x" not in _agent._pending_hop_attempts
        mock_late.assert_not_called()

    def test_hop_classification_parks_pending(self):
        hop = _agent._ClassifyResult(is_hop=True, confidence=90, reason="discord invite", via="server")

        with patch.object(_agent, "_classify", return_value=hop), \
             patch.object(_agent, "_try_late_confirm"):
            _agent._decide_and_send(
                "https://discord.gg/abc", "ctx", "roblox.exe", "Roblox", "ocr",
                time.monotonic(),
            )

        assert "https://discord.gg/abc" in _agent._pending_hop_attempts
        entry = _agent._pending_hop_attempts["https://discord.gg/abc"]
        assert entry["from"] == "roblox.exe"
        assert entry["to"] == "https://discord.gg/abc"
        assert entry["classifyConfidence"] == 90

    def test_hop_classification_calls_try_late_confirm_with_correct_args(self):
        hop = _agent._ClassifyResult(is_hop=True, confidence=90, reason="invite", via="server")
        detected_at = time.monotonic() - 3.0

        with patch.object(_agent, "_classify", return_value=hop), \
             patch.object(_agent, "_try_late_confirm") as mock_late:
            _agent._decide_and_send(
                "https://discord.gg/abc", "ctx", "roblox.exe", "Roblox", "ocr",
                detected_at,
            )

        mock_late.assert_called_once_with("roblox.exe", detected_at)

    def test_server_error_does_not_park_pending(self):
        error = _agent._ClassifyResult(is_hop=False, confidence=0, reason="server_unreachable", via="error")

        with patch.object(_agent, "_classify", return_value=error), \
             patch.object(_agent, "_try_late_confirm") as mock_late:
            _agent._decide_and_send(
                "https://discord.gg/abc", "ctx", "roblox.exe", "Roblox", "ocr",
                time.monotonic(),
            )

        assert "https://discord.gg/abc" not in _agent._pending_hop_attempts
        mock_late.assert_not_called()

    def test_detected_at_forwarded_exactly_to_try_late_confirm(self):
        """detected_at must reach _try_late_confirm unchanged — no re-stamping."""
        hop = _agent._ClassifyResult(is_hop=True, confidence=80, reason="lure", via="server")
        detected_at = time.monotonic() - 7.3

        with patch.object(_agent, "_classify", return_value=hop), \
             patch.object(_agent, "_try_late_confirm") as mock_late:
            _agent._decide_and_send(
                "https://t.me/x", "ctx", "roblox.exe", "Roblox", "clipboard",
                detected_at,
            )

        _game_proc_arg, detected_at_arg = mock_late.call_args[0]
        assert detected_at_arg == detected_at

    def test_classify_called_with_correct_detection_source(self):
        safe = _agent._ClassifyResult(is_hop=False, confidence=0, reason="clean", via="server")

        with patch.object(_agent, "_classify", return_value=safe) as mock_classify:
            _agent._decide_and_send(
                "https://discord.gg/abc", "some context", "roblox.exe", "Roblox", "clipboard",
                time.monotonic(),
            )

        mock_classify.assert_called_once_with("https://discord.gg/abc", "some context", "clipboard")

    def test_pending_stores_classify_reason_and_source(self):
        hop = _agent._ClassifyResult(is_hop=True, confidence=85, reason="telegram invite link", via="server")

        with patch.object(_agent, "_classify", return_value=hop), \
             patch.object(_agent, "_try_late_confirm"):
            _agent._decide_and_send(
                "https://t.me/xyz", "ctx", "roblox.exe", "Roblox", "ocr",
                time.monotonic(),
            )

        entry = _agent._pending_hop_attempts["https://t.me/xyz"]
        assert entry["classifyReason"] == "telegram invite link"
        assert entry["classifySource"] == "server"

    def test_multiple_urls_each_get_own_pending_entry(self):
        hop = _agent._ClassifyResult(is_hop=True, confidence=90, reason="lure", via="server")

        with patch.object(_agent, "_classify", return_value=hop), \
             patch.object(_agent, "_try_late_confirm"):
            _agent._decide_and_send(
                "https://discord.gg/a", "ctx", "roblox.exe", "Roblox", "ocr",
                time.monotonic(),
            )
            _agent._decide_and_send(
                "https://t.me/b", "ctx", "roblox.exe", "Roblox", "ocr",
                time.monotonic(),
            )

        assert "https://discord.gg/a" in _agent._pending_hop_attempts
        assert "https://t.me/b" in _agent._pending_hop_attempts
        assert len(_agent._pending_hop_attempts) == 2


# ---------------------------------------------------------------------------
# _drain_and_confirm
# ---------------------------------------------------------------------------

class TestDrainAndConfirm:

    def test_empty_pending_does_not_call_confirm(self):
        with patch.object(_agent, "_confirm_pending") as mock_confirm:
            _agent._drain_and_confirm("discord.exe", "Discord", 1001)

        mock_confirm.assert_not_called()

    def test_confirms_all_pending_entries(self):
        pending_a = _make_pending("https://discord.gg/a")
        pending_b = _make_pending("https://t.me/b")
        _agent._pending_hop_attempts["https://discord.gg/a"] = pending_a
        _agent._pending_hop_attempts["https://t.me/b"] = pending_b

        with patch.object(_agent, "_confirm_pending") as mock_confirm:
            _agent._drain_and_confirm("discord.exe", "Discord", 1001)

        assert mock_confirm.call_count == 2
        confirmed_pendings = {call.args[0]["to"] for call in mock_confirm.call_args_list}
        assert confirmed_pendings == {"https://discord.gg/a", "https://t.me/b"}

    def test_confirm_pending_receives_correct_proc_title_hwnd(self):
        _agent._pending_hop_attempts["https://discord.gg/a"] = _make_pending()

        with patch.object(_agent, "_confirm_pending") as mock_confirm:
            _agent._drain_and_confirm("discord.exe", "Discord", 9999)

        _, proc, title, hwnd = mock_confirm.call_args[0]
        assert proc == "discord.exe"
        assert title == "Discord"
        assert hwnd == 9999

    def test_pending_cleared_before_confirm_is_invoked(self):
        """The dict is empty by the time _confirm_pending runs, so a concurrent
        caller that acquires the lock after us finds nothing and exits cleanly."""
        _agent._pending_hop_attempts["https://discord.gg/a"] = _make_pending()
        pending_len_during_confirm = []

        def capture_state(pending, proc, title, hwnd):
            pending_len_during_confirm.append(len(_agent._pending_hop_attempts))

        with patch.object(_agent, "_confirm_pending", side_effect=capture_state):
            _agent._drain_and_confirm("discord.exe", "Discord", 1001)

        assert pending_len_during_confirm == [0]

    def test_concurrent_callers_confirm_each_entry_exactly_once(self):
        """Lock guarantees snapshot-and-clear: only one caller wins the dict."""
        _agent._pending_hop_attempts["https://discord.gg/a"] = _make_pending()
        confirm_calls: list[str] = []
        barrier = threading.Barrier(2)

        def slow_confirm(pending, proc, title, hwnd):
            time.sleep(0.02)
            confirm_calls.append(pending["to"])

        def call_drain():
            barrier.wait()  # both threads enter _drain_and_confirm simultaneously
            _agent._drain_and_confirm("discord.exe", "Discord", 1001)

        with patch.object(_agent, "_confirm_pending", side_effect=slow_confirm):
            t1 = threading.Thread(target=call_drain)
            t2 = threading.Thread(target=call_drain)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        assert len(confirm_calls) == 1
