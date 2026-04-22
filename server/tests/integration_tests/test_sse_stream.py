"""Integration tests for GET /stream/{child_id} — Server-Sent Events endpoint.

Uses a real uvicorn server in a background thread so that SSE streaming works
correctly.  The app is configured by the global `_global_test_setup` fixture
in tests/conftest.py.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest
import requests
import uvicorn
from starlette.testclient import TestClient

_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
_TESTS_DIR = _SERVER_DIR / "tests"
for _p in (_SERVER_DIR, _TESTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from test_helpers import find_free_port, register_test_child

# The app singleton is already configured by _global_test_setup.
from server import app as _app


# ---------------------------------------------------------------------------
# Module-scoped real uvicorn server fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def live_sse_server(_global_test_setup):
    """Start the mocked app on a real uvicorn port in a background thread."""
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(_app, host="127.0.0.1", port=port, log_level="error", ws="wsproto")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            requests.get(f"{base_url}/health", timeout=1)
            break
        except requests.ConnectionError:
            time.sleep(0.1)
    else:
        pytest.fail("SSE test server did not start within 10 seconds.")

    yield base_url

    server.should_exit = True
    thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_sse(base_url: str, child_id: str, max_events: int = 1,
                 timeout: float = 5.0) -> list[dict]:
    """Open a real HTTP SSE stream, collect up to *max_events* data frames, then close."""
    collected: list[dict] = []
    with requests.get(
        f"{base_url}/stream/{child_id}", stream=True, timeout=timeout
    ) as response:
        assert response.status_code == 200
        for raw_line in response.iter_lines():
            line = raw_line.decode() if isinstance(raw_line, bytes) else raw_line
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload:
                    try:
                        collected.append(json.loads(payload))
                    except json.JSONDecodeError:
                        pass
            if len(collected) >= max_events:
                break
    return collected


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_sse_history_message_on_connect(live_sse_server):
    """Connecting to /stream/{child_id} must immediately yield a history event."""
    base_url = live_sse_server
    register_test_child("sse-test-kid")
    events = _collect_sse(base_url, "sse-test-kid", max_events=1)

    assert len(events) == 1
    assert events[0]["type"] == "history"
    assert "events" in events[0]


def test_sse_history_contains_existing_events(live_sse_server):
    """Events already in DB at connect time should appear in the history message."""
    base_url = live_sse_server
    child = "history-content-kid"
    register_test_child(child)

    import events.repository as _evt_repo
    _evt_repo._col_events().delete_many({"childId": child})
    _evt_repo.insert_event({
        "childId": child,
        "from": "roblox.exe",
        "to": "discord.exe",
        "timestamp": "2026-01-01T12:00:00Z",
        "alert": True,
        "alertReason": "confirmed_hop",
    })

    events = _collect_sse(base_url, child, max_events=1)

    assert len(events) == 1
    history = events[0]
    assert history["type"] == "history"
    assert len(history["events"]) == 1
    assert history["events"][0]["from"] == "roblox.exe"


def test_sse_ping_heartbeat_received(live_sse_server, monkeypatch):
    """The keep-alive heartbeat (': ping') should be emitted within 2 s (patched interval)."""
    import events.router as _sse_router
    monkeypatch.setattr(_sse_router, "_HEARTBEAT_INTERVAL", 0.2)

    base_url = live_sse_server
    register_test_child("ping-test-kid")
    ping_received = False
    with requests.get(f"{base_url}/stream/ping-test-kid", stream=True, timeout=5.0) as resp:
        assert resp.status_code == 200
        for raw_line in resp.iter_lines():
            line = raw_line.decode() if isinstance(raw_line, bytes) else raw_line
            if line == ": ping":
                ping_received = True
                break
    assert ping_received, "No SSE heartbeat ping received within timeout"


def test_sse_invalid_child_id_returns_400():
    with TestClient(_app) as client:
        resp = client.get("/stream/bad id!")
    assert resp.status_code == 400
