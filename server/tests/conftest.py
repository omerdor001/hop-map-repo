"""
Global pytest configuration and fixtures for all HopMap server tests.

Unit tests (server/tests/unit_tests/)
    - Import server functions directly; no server process needed.
    - Use the `words_db_path` / `platforms_db_path` fixtures for real Excel files.

Integration / E2E tests (server/tests/integration_tests/, server/tests/e2e/)
    - All external deps (MongoDB, LLM) are replaced at session start by
      `_global_test_setup`.  Individual test modules should NOT call their
      own setup helpers at module level — doing so would overwrite the shared
      singletons and break other test modules running in the same session.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import mongomock
import pytest
import requests
import uvicorn

# Make server/ importable from any test subfolder.
_SERVER_DIR = Path(__file__).resolve().parent.parent
_TESTS_DIR  = Path(__file__).resolve().parent
for _p in (_SERVER_DIR, _TESTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# When the full test suite runs from the repo root, agent/ is collected before
# server/ (alphabetical order).  Agent test files import agent.py, which does
# `from config import config_manager`, caching *agent/config.py* in
# sys.modules['config'].  Evict it here so server/config.py is imported fresh
# when server modules are first loaded during this conftest's own imports.
_cached_config = sys.modules.get("config")
if _cached_config is not None:
    _cached_file = getattr(_cached_config, "__file__", "") or ""
    if str(_SERVER_DIR) not in _cached_file:
        sys.modules.pop("config", None)

# Must be module-level so `from __future__ import annotations` doesn't hide
# it from FastAPI's get_type_hints() when resolving _mock_agent_child's signature.
from fastapi import Request as _FastAPIRequest

from test_helpers import DEFAULT_BASE_URL, find_free_port


# ---------------------------------------------------------------------------
# Unit-test fixtures — inject real data-file paths from server/data/
# ---------------------------------------------------------------------------

_DATA_DIR = _SERVER_DIR / "data"


@pytest.fixture(scope="session")
def words_db_path() -> str:
    p = _DATA_DIR / "hopmap_words_db.xlsx"
    if not p.exists():
        pytest.skip(f"Words DB not found: {p}")
    return str(p)


@pytest.fixture(scope="session")
def platforms_db_path() -> str:
    p = _DATA_DIR / "platforms_db.xlsx"
    if not p.exists():
        pytest.skip(f"Platforms DB not found: {p}")
    return str(p)


# ---------------------------------------------------------------------------
# Session-level test infrastructure — runs ONCE before any test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _global_test_setup():
    """Wire all shared singletons for the test session.

    Replaces the real MongoDB connection with mongomock, installs auth
    dependency overrides so tests don't need JWT tokens, and seeds a
    predictable LLM mock.  This fixture runs after all modules are
    imported (pytest guarantee), so it is safe to overwrite any
    module-level state set by test-module builder functions.
    """
    import core.database as _db_mod

    mock_client = mongomock.MongoClient()
    _db_mod._pool._client = mock_client
    _db_mod._pool._db = mock_client[_db_mod._pool.db_name]

    import words.service as _words_svc
    _words_svc._filter.build(set())

    import classify.service as _cls_svc
    mock_llm = MagicMock()
    mock_llm.classify.return_value = {
        "decision": "NO",
        "confidence": 5,
        "reason": "clean content",
    }
    _cls_svc.set_llm(mock_llm)

    from server import app
    from auth.dependencies import get_agent_child, get_current_user

    _TEST_USER = {
        "id": "test-parent-id",
        "email": "test@hopmap.test",
        "displayName": "Test Parent",
        "maxChildren": 100,
    }

    async def _mock_current_user() -> dict:
        return _TEST_USER

    async def _mock_agent_child(request: _FastAPIRequest) -> dict:
        child_id = request.path_params.get("child_id", "")
        if not child_id:
            try:
                body_bytes = await request.body()
                body_data = json.loads(body_bytes)
                child_id = body_data.get("childId", "test-child")
            except Exception:
                child_id = "test-child"
        return {
            "childId": child_id,
            "parentId": "test-parent-id",
            "childName": "Test Child",
        }

    app.dependency_overrides[get_current_user] = _mock_current_user
    app.dependency_overrides[get_agent_child] = _mock_agent_child

    yield mock_llm


# ---------------------------------------------------------------------------
# Integration-test fixture — live FastAPI server in a background thread
# (kept for backwards-compatibility; not used by current test suite)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def live_server(_global_test_setup):
    """Start the HopMap FastAPI server on a free port for the test session."""
    try:
        r = requests.get(f"{DEFAULT_BASE_URL}/api/children", timeout=2)
        if r.status_code < 500:
            yield DEFAULT_BASE_URL
            return
    except requests.ConnectionError:
        pass

    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    from server import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            requests.get(f"{base_url}/api/children", timeout=1)
            break
        except requests.ConnectionError:
            time.sleep(0.2)
    else:
        pytest.fail("Test server did not start within 10 seconds.")

    yield base_url

    server.should_exit = True
    thread.join(timeout=5)
