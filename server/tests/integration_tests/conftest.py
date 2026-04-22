"""
Pytest configuration for TestClient-based integration tests.

The heavy setup (mongomock, LLM mock, auth overrides) is done once at
session level by the global `_global_test_setup` fixture in tests/conftest.py.
This file only provides per-module and per-test fixtures for app access and
state cleanup.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))


@pytest.fixture(scope="module")
def _app(_global_test_setup):
    """Return the configured FastAPI app (session-level setup already done)."""
    from server import app
    return app


@pytest.fixture()
def app_client(_app, _global_test_setup):
    """Yield a TestClient for the mocked app with clean state per test."""
    mock_llm = _global_test_setup

    import classify.service as cls_svc
    import events.service as _evt_svc
    import words.service as words_svc

    _evt_svc._sse_queues.clear()
    cls_svc._classify_call_times.clear()
    mock_llm.reset_mock()

    from core.rate_limit import limiter
    limiter._storage.reset()
    mock_llm.classify.return_value = {
        "decision": "NO",
        "confidence": 5,
        "reason": "clean content",
    }

    from core.database import pool
    from config import config_manager
    try:
        pool.get_collection(config_manager.db.events_collection).delete_many({})
        pool.get_collection("children").delete_many({})
        pool.get_collection(config_manager.db.words_collection).delete_many({})
    except Exception:
        pass

    with TestClient(_app, raise_server_exceptions=True) as client:
        yield client, {"llm": mock_llm, "words_svc": words_svc, "cls_svc": cls_svc}
