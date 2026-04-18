"""
Pytest configuration for agent tests.

agent.py imports several Windows-only packages at module level:
  winreg, ctypes.windll, win32gui, win32process, mss, pytesseract, pyperclip

We inject stub modules into sys.modules BEFORE agent.py is imported so that
the test suite runs on any platform (Linux/macOS CI included).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# Ensure agent/ is importable.
_AGENT_DIR = Path(__file__).resolve().parent.parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))


def _make_stub(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    return mod


# ---------------------------------------------------------------------------
# Stub out Windows-only / external modules before any agent import
# ---------------------------------------------------------------------------

_STUBS = {
    "winreg":           MagicMock(),
    "win32gui":         MagicMock(),
    "win32process":     MagicMock(),
    "mss":              MagicMock(),
    "pytesseract":      MagicMock(),
    "pyperclip":        MagicMock(),
    "psutil":           MagicMock(),
    "PIL":              MagicMock(),
    "PIL.Image":        MagicMock(),
}

# Make ctypes.windll available without a real Win32 environment.
import ctypes as _ctypes  # noqa: E402  (standard lib — always available)
if not hasattr(_ctypes, "windll"):
    _ctypes.windll = MagicMock()
if not hasattr(_ctypes, "wintypes"):
    _ctypes.wintypes = MagicMock()

for _name, _stub in _STUBS.items():
    sys.modules.setdefault(_name, _stub)

# pytesseract.pytesseract sub-module must also be stubbed so
# _configure_tesseract() doesn't raise AttributeError.
_tesseract_inner = MagicMock()
_tesseract_inner.tesseract_cmd = "tesseract"
sys.modules.setdefault("pytesseract.pytesseract", _tesseract_inner)
sys.modules["pytesseract"].pytesseract = _tesseract_inner  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Pre-load agent modules by absolute path.
#
# Both agent/config.py and server/config.py export a module named "config".
# When both test suites run together, whichever conftest inserts its
# directory into sys.path last wins the "config" name race.  To side-step
# that race we pre-load our modules by path and cache them in sys.modules
# BEFORE any test-file collection can trigger the wrong import.
# ---------------------------------------------------------------------------
import importlib.util as _ilu

# 1. agent/config.py → sys.modules["config"]
if "config" not in sys.modules:
    _cfg_spec = _ilu.spec_from_file_location("config", _AGENT_DIR / "config.py")
    _cfg_mod = _ilu.module_from_spec(_cfg_spec)
    sys.modules["config"] = _cfg_mod
    _cfg_spec.loader.exec_module(_cfg_mod)

# 2. agent/agent.py → sys.modules["agent"]
#    Must happen AFTER config is cached so agent.py's module-level
#    `BACKEND_URL = config_manager.backend_url` finds the right config.
if "agent" not in sys.modules:
    _agent_spec = _ilu.spec_from_file_location("agent", _AGENT_DIR / "agent.py")
    _agent_mod = _ilu.module_from_spec(_agent_spec)
    sys.modules["agent"] = _agent_mod      # cache before exec to handle self-imports
    _agent_spec.loader.exec_module(_agent_mod)
