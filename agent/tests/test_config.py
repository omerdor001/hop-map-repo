"""Unit tests for AgentConfig (agent/config.py).

Verifies default values, URL normalisation, and env-var override, all
without touching the real agent_config.json so tests are self-contained.
"""
from __future__ import annotations

import importlib.util as _ilu
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure agent/ is importable (already handled by conftest but safe to repeat).
_AGENT_DIR = Path(__file__).resolve().parent.parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

# Load agent/config.py by absolute path so we always get the agent's config
# module — not server/config.py — regardless of sys.modules["config"] state.
_AGENT_CONFIG_PATH = _AGENT_DIR / "config.py"


def _load_config(json_overrides: dict | None = None, env_overrides: dict | None = None,
                 tmp_path: Path | None = None):
    """Helper: create a temp agent_config.json and return a fresh AgentConfig."""
    # Load a fresh, isolated copy of agent/config.py by path so it is never
    # confused with server/config.py (they share the module name "config").
    spec = _ilu.spec_from_file_location("_agent_cfg_tmp", _AGENT_CONFIG_PATH)
    cfg_mod = _ilu.module_from_spec(spec)

    # Write a temporary config JSON.
    defaults = {
        "backend_url": "http://localhost:8000",
        "scan_interval_seconds": 5.0,
        "context_lines": 10,
    }
    if json_overrides:
        defaults.update(json_overrides)

    if tmp_path is None:
        import tempfile
        _tmp = Path(tempfile.mkdtemp())
    else:
        _tmp = tmp_path

    config_file = _tmp / "agent_config.json"
    config_file.write_text(json.dumps(defaults), encoding="utf-8")

    env = {f"HOPMAP_AGENT__{k.upper()}": str(v) for k, v in (env_overrides or {}).items()}

    # Execute the module with _CONFIG_FILE already pointing at our temp file.
    # We set it on the module object before exec so the class definition picks
    # up the correct path from its module globals.
    spec.loader.exec_module(cfg_mod)
    cfg_mod._CONFIG_FILE = config_file
    try:
        with patch.dict(os.environ, env, clear=False):
            return cfg_mod.AgentConfig()
    finally:
        cfg_mod._CONFIG_FILE = _AGENT_CONFIG_PATH


class TestAgentConfigDefaults:

    def test_default_backend_url(self, tmp_path):
        cfg = _load_config(tmp_path=tmp_path)
        assert cfg.backend_url == "http://localhost:8000"

    def test_default_scan_interval(self, tmp_path):
        cfg = _load_config(tmp_path=tmp_path)
        assert cfg.scan_interval_seconds == 5.0

    def test_default_context_lines(self, tmp_path):
        cfg = _load_config(tmp_path=tmp_path)
        assert cfg.context_lines == 10


class TestAgentConfigUrlNormalisation:

    def test_trailing_slash_stripped(self, tmp_path):
        cfg = _load_config({"backend_url": "http://192.168.1.10:8000/"}, tmp_path=tmp_path)
        assert not cfg.backend_url.endswith("/")

    def test_multiple_trailing_slashes_stripped(self, tmp_path):
        cfg = _load_config({"backend_url": "http://example.com///"}, tmp_path=tmp_path)
        assert not cfg.backend_url.endswith("/")

    def test_url_without_trailing_slash_unchanged(self, tmp_path):
        cfg = _load_config({"backend_url": "http://example.com:9000"}, tmp_path=tmp_path)
        assert cfg.backend_url == "http://example.com:9000"


class TestAgentConfigFromJson:

    def test_custom_backend_url_loaded(self, tmp_path):
        cfg = _load_config({"backend_url": "http://192.168.0.5:8080"}, tmp_path=tmp_path)
        assert "192.168.0.5" in cfg.backend_url

    def test_custom_scan_interval_loaded(self, tmp_path):
        cfg = _load_config({"scan_interval_seconds": 3.0}, tmp_path=tmp_path)
        assert cfg.scan_interval_seconds == 3.0

    def test_custom_context_lines_loaded(self, tmp_path):
        cfg = _load_config({"context_lines": 5}, tmp_path=tmp_path)
        assert cfg.context_lines == 5
