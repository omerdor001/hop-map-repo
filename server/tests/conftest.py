"""
Global pytest configuration and fixtures for all HopMap server tests.

Unit tests (server/tests/unit_tests/)
    - Import server functions directly; no server process needed.
    - Use the `words_db_path` / `platforms_db_path` fixtures for real Excel files.

Integration tests (server/tests/integration_tests/)
    - Use the `live_server` fixture which starts FastAPI via uvicorn in a
      background thread on a free port, then tears it down after the session.
    - Each test module registers its own child via POST /api/children.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest
import requests
import uvicorn

# Make server/ and server/tests/ importable from any test subfolder.
_SERVER_DIR = Path(__file__).resolve().parent.parent
_TESTS_DIR  = Path(__file__).resolve().parent
for _p in (_SERVER_DIR, _TESTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from test_helpers import DEFAULT_BASE_URL, find_free_port


# ---------------------------------------------------------------------------
# Unit-test fixtures — inject real data-file paths from server/data/
# ---------------------------------------------------------------------------

_DATA_DIR = _SERVER_DIR / "data"


@pytest.fixture(scope="session")
def words_db_path() -> str:
    """Absolute path to the real hopmap_words_db.xlsx used by the server."""
    p = _DATA_DIR / "hopmap_words_db.xlsx"
    if not p.exists():
        pytest.skip(f"Words DB not found: {p}")
    return str(p)


@pytest.fixture(scope="session")
def platforms_db_path() -> str:
    """Absolute path to the real platforms_db.xlsx used by the server."""
    p = _DATA_DIR / "platforms_db.xlsx"
    if not p.exists():
        pytest.skip(f"Platforms DB not found: {p}")
    return str(p)


# ---------------------------------------------------------------------------
# Integration-test fixture — live FastAPI server in a background thread
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def live_server():
    """Start the HopMap FastAPI server on a free port for the test session.

    Yields a base URL string, e.g. ``http://127.0.0.1:54321``.
    The server is shut down after all tests finish.

    If a server is already running on DEFAULT_BASE_URL (e.g. the dev server),
    that instance is reused and nothing new is spawned.
    """
    # Re-use an already-running dev server rather than spawning a second one.
    try:
        r = requests.get(f"{DEFAULT_BASE_URL}/api/children", timeout=2)
        if r.status_code < 500:
            yield DEFAULT_BASE_URL
            return
    except requests.ConnectionError:
        pass

    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    from server import app  # import here so sys.path is already patched

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait until the server is accepting connections (up to 10 s).
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
