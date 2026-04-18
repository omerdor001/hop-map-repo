"""End-to-end tests: full HTTP request chain through the real FastAPI app.

All external dependencies (MongoDB, Ollama) are mocked at session level by
the global `_global_test_setup` fixture in tests/conftest.py.
Tests exercise complete user flows: classify → hop → events → SSE broadcast.
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

from test_helpers import find_free_port

# The app singleton is already configured by _global_test_setup (tests/conftest.py).
from server import app as _e2e_app


# ---------------------------------------------------------------------------
# Helpers to access shared mocks set up by _global_test_setup
# ---------------------------------------------------------------------------

def _llm():
    import classify.service as _svc
    return _svc._llm


# ---------------------------------------------------------------------------
# Per-test state reset
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_state(_global_test_setup):
    """Reset all mutable server state before each E2E test."""
    mock_llm = _global_test_setup

    import classify.service as _cls_svc
    import events.service as _evt_svc
    import words.service as _words_svc
    from core.database import _pool
    from config import config_manager

    # Re-install mock LLM in case a previous test's TestClient lifespan overwrote it.
    _cls_svc.set_llm(mock_llm)

    _evt_svc._sse_queues.clear()
    _cls_svc._classify_call_times.clear()
    mock_llm.reset_mock()
    mock_llm.classify.return_value = {
        "decision": "NO",
        "confidence": 5,
        "reason": "clean content",
    }
    _words_svc._filter.build(set())

    _pool.get_collection(config_manager.db.events_collection).delete_many({})
    _pool.get_collection("children").delete_many({})
    _pool.get_collection(config_manager.db.words_collection).delete_many({})
    yield


@pytest.fixture()
def client(_global_test_setup):
    mock_llm = _global_test_setup
    with TestClient(_e2e_app, raise_server_exceptions=True) as c:
        # Re-apply mock after lifespan runs (lifespan calls set_llm with real provider).
        import classify.service as _cls_svc
        _cls_svc.set_llm(mock_llm)
        yield c


@pytest.fixture(scope="module")
def sse_server(_global_test_setup):
    """Start _e2e_app on a real uvicorn port in a background thread."""
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(_e2e_app, host="127.0.0.1", port=port, log_level="error")
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
        pytest.fail("E2E SSE test server did not start within 10 seconds.")

    yield base_url

    server.should_exit = True
    thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Flow 1: Classify with blocked word → words_db path
# ---------------------------------------------------------------------------

class TestClassifyBlockedWordFlow:

    def test_classify_blocked_word_returns_yes_via_word_db(self, client):
        """When context contains a blocked word, LLM must be skipped."""
        client.post("/api/words", json={"word": "discord"})

        resp = client.post("/agent/classify", json={
            "childId": "e2e-kid",
            "url": "https://discord.gg/abc",
            "context": "Join my discord server!",
            "source": "ocr",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "YES"
        assert data["via"] == "word_db"
        _llm().classify.assert_not_called()

    def test_classify_clean_context_routes_to_llm(self, client):
        """Without a blocked word, the LLM must be invoked."""
        _llm().classify.return_value = {
            "decision": "NO",
            "confidence": 10,
            "reason": "game wiki link",
        }
        resp = client.post("/agent/classify", json={
            "childId": "e2e-kid",
            "url": "https://minecraft.net/wiki",
            "context": "Check the wiki for crafting recipes.",
            "source": "clipboard",
        })
        assert resp.status_code == 200
        assert resp.json()["decision"] == "NO"
        _llm().classify.assert_called_once()


# ---------------------------------------------------------------------------
# Flow 2: Hop ingestion → event retrieval
# ---------------------------------------------------------------------------

class TestHopToEventFlow:

    def test_hop_ingested_then_retrievable(self, client):
        child = "e2e-hop-kid"
        client.post(f"/agent/hop/{child}", json={
            "from": "robloxplayerbeta.exe",
            "to": "discord.exe",
            "detection": "confirmed_hop",
            "clickConfidence": "app_match",
        })
        events = client.get(f"/api/events/{child}").json()
        assert events["count"] == 1
        assert events["events"][0]["from"] == "robloxplayerbeta.exe"

    def test_events_cleared_after_delete(self, client):
        child = "e2e-clear-kid"
        client.post(f"/agent/hop/{child}", json={
            "from": "game.exe",
            "to": "discord.exe",
            "detection": "confirmed_hop",
            "clickConfidence": "app_match",
        })
        client.delete(f"/api/events/{child}")
        events = client.get(f"/api/events/{child}").json()
        assert events["count"] == 0

    def test_multi_child_events_isolated(self, client):
        """Events for child A must not appear for child B."""
        for child in ("e2e-kid-a", "e2e-kid-b"):
            client.post(f"/agent/hop/{child}", json={
                "from": "game.exe", "to": "discord.exe",
                "detection": "confirmed_hop", "clickConfidence": "app_match",
            })
        assert client.get("/api/events/e2e-kid-a").json()["count"] == 1
        assert client.get("/api/events/e2e-kid-b").json()["count"] == 1


# ---------------------------------------------------------------------------
# Flow 3: Child registration → list
# ---------------------------------------------------------------------------

class TestChildRegistrationFlow:

    def test_register_then_list(self, client):
        client.post("/api/children", json={"childId": "e2e-reg-kid", "childName": "Tester"})
        children = {c["childId"] for c in client.get("/api/children").json()["children"]}
        assert "e2e-reg-kid" in children

    def test_register_rename_verify(self, client):
        client.post("/api/children", json={"childId": "e2e-rename-kid", "childName": "OldName"})
        client.patch("/api/children/e2e-rename-kid", json={"childName": "NewName"})
        children = {c["childId"]: c["childName"]
                    for c in client.get("/api/children").json()["children"]}
        assert children.get("e2e-rename-kid") == "NewName"


# ---------------------------------------------------------------------------
# Flow 4: Rate limiter — 31st classify call returns 429
# ---------------------------------------------------------------------------

class TestRateLimiterFlow:

    def test_31st_classify_returns_429(self, client):
        payload = {
            "childId": "rate-kid",
            "url": "https://example.com/x",
            "context": "test context",
            "source": "ocr",
        }
        for _ in range(30):
            resp = client.post("/agent/classify", json=payload)
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

        resp = client.post("/agent/classify", json=payload)
        assert resp.status_code == 429

    def test_rate_limit_is_per_child(self, client):
        """Maxing out one child's rate must not affect another."""
        payload_a = {"childId": "rl-kid-a", "url": "https://x.com/a", "context": "x", "source": "ocr"}
        payload_b = {"childId": "rl-kid-b", "url": "https://x.com/b", "context": "y", "source": "ocr"}

        for _ in range(30):
            client.post("/agent/classify", json=payload_a)

        assert client.post("/agent/classify", json=payload_a).status_code == 429
        assert client.post("/agent/classify", json=payload_b).status_code == 200


# ---------------------------------------------------------------------------
# Flow 5: SSE broadcast — hop event reaches live listener
# ---------------------------------------------------------------------------

def test_sse_broadcast_after_hop(sse_server):
    """POST a hop then verify the SSE stream delivers it to a connected listener."""
    base_url = sse_server
    child = "e2e-sse-kid"

    import events.service as _evt_svc
    _evt_svc._sse_queues.clear()

    received: list[dict] = []
    got_two = threading.Event()

    def _listen():
        with requests.get(
            f"{base_url}/stream/{child}", stream=True, timeout=10.0
        ) as r:
            for raw_line in r.iter_lines():
                line = raw_line.decode() if isinstance(raw_line, bytes) else raw_line
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    if payload:
                        try:
                            received.append(json.loads(payload))
                        except json.JSONDecodeError:
                            pass
                if len(received) >= 2:
                    got_two.set()
                    break

    listener = threading.Thread(target=_listen, daemon=True)
    listener.start()

    time.sleep(0.3)

    requests.post(f"{base_url}/agent/hop/{child}", json={
        "from": "roblox.exe",
        "to": "discord.exe",
        "detection": "confirmed_hop",
        "clickConfidence": "app_match",
    })

    got_two.wait(timeout=5)
    listener.join(timeout=5)

    types = [e.get("type") for e in received]
    assert "history" in types
    assert "event" in types


def test_sse_multi_child_isolation(sse_server):
    """Events for child A must not be delivered to child B's SSE stream."""
    base_url = sse_server
    child_a = "iso-kid-a"
    child_b = "iso-kid-b"

    import events.service as _evt_svc
    _evt_svc._sse_queues.clear()

    events_b: list[dict] = []
    history_received = threading.Event()

    def _listen_b():
        try:
            with requests.get(
                f"{base_url}/stream/{child_b}",
                stream=True,
                timeout=(5.0, 2.0),
            ) as r:
                for raw_line in r.iter_lines():
                    line = raw_line.decode() if isinstance(raw_line, bytes) else raw_line
                    if line.startswith("data:"):
                        payload = line[5:].strip()
                        if payload:
                            try:
                                events_b.append(json.loads(payload))
                            except json.JSONDecodeError:
                                pass
                    if any(e.get("type") == "history" for e in events_b):
                        history_received.set()
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
            pass
        finally:
            history_received.set()

    listener = threading.Thread(target=_listen_b, daemon=True)
    listener.start()

    history_received.wait(timeout=5)

    requests.post(f"{base_url}/agent/hop/{child_a}", json={
        "from": "game.exe",
        "to": "discord.exe",
        "detection": "confirmed_hop",
        "clickConfidence": "app_match",
    })

    listener.join(timeout=5)

    for e in events_b:
        if e.get("type") == "event":
            pytest.fail(f"child_b received an event intended for child_a: {e}")
