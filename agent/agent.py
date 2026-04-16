"""
HopMap Desktop Agent — runs on the kid's Windows PC.

This process is intentionally a lightweight sensor.  It does no LLM work
locally.  All classification is delegated to the HopMap server via a single
POST /agent/classify call, keeping GPU and CPU load off the child's machine
during active gaming sessions.

Detection pipeline
──────────────────
  Layer 0 — Win32 SetWinEventHook fires on every foreground-window change.
             The ctypes callback is a two-liner: it enqueues the raw HWND and
             returns immediately so Windows never coalesces or drops events.

  Layer 1 — A dedicated event-processor thread drains the HWND queue and
             drives all business logic (scanner lifecycle, pending-hop
             confirmation, plain hop reporting).

  Layer 2 — While a recognised game owns the foreground a scanner thread
             periodically screenshots that window and runs Tesseract OCR on it.
             A URL regex extracts every candidate link from the raw text.

  Layer 3 — A clipboard monitor thread polls the system clipboard every second
             and applies the same URL extraction.  This catches the common
             "copy this link and open it" lure that is invisible to OCR.

  Layer 4 — Every new URL (de-duplicated via a TTL cache so re-appearing links
             are re-evaluated after the TTL expires) triggers a POST to
             /agent/classify on the HopMap server.  The server runs the LLM and
             returns { decision, confidence, reason }.
             If the server is unreachable the URL is treated as safe and skipped,
             preventing false positives at the cost of missed detections during
             network outages.

  Layer 5 — When the server (or fallback) flags a hop attempt the lure is
             parked in a per-URL pending store.  On the next app-switch away
             from the game the store is drained and each lure is confirmed with
             one of three click-confidence tiers:
               • app_match   — the native desktop app for the lure platform opened
               • title_match — a browser navigated to the lure domain (title poll)
               • switch_only — an app switch occurred but no stronger signal

Required packages (pip install):
    pywin32  psutil  requests  python-dotenv  mss  pytesseract  Pillow
    ollama   pyperclip

Tesseract OCR engine (used by the local Ollama fallback only):
    https://github.com/UB-Mannheim/tesseract/wiki

Run with:
    pythonw agent.py    # hides the console — recommended for production
    python  agent.py    # shows the console — useful for debugging
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import logging
import os
import pathlib
import queue
import re
import shutil
import threading
import time
import winreg
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import mss
import psutil
import pyperclip
import pytesseract
import requests
import win32gui
import win32process
from PIL import Image

from config import config_manager

# ---------------------------------------------------------------------------
# Platform & Process Database (fetched from server on startup)
# ---------------------------------------------------------------------------
# The server loads platforms_db.xlsx and exposes GET /api/platforms.
# The agent fetches it once at startup so no data files are needed on the
# child's machine.  If the server is unreachable the hardcoded fallbacks
# below are used so the agent still starts normally.

# Built-in defaults — used when the server is unreachable at startup.
_PLATFORM_APP_MAP_DEFAULT: dict[str, frozenset[str]] = {
    "discord":   frozenset({"discord.exe"}),
    "telegram":  frozenset({"telegram.exe", "telegramdesktop.exe"}),
    "whatsapp":  frozenset({"whatsapp.exe", "whatsapp.root.exe"}),
    "signal":    frozenset({"signal.exe"}),
    "snapchat":  frozenset({"snapchat.exe"}),
    "instagram": frozenset(),   # web / mobile only on desktop
    "tiktok":    frozenset(),
    "youtube":   frozenset(),
    "twitch":    frozenset(),
}

_BROWSER_PROCESSES_DEFAULT: frozenset[str] = frozenset({
    "chrome.exe", "msedge.exe", "firefox.exe",
    "opera.exe",  "brave.exe",  "vivaldi.exe",
})

_TRANSIT_PROCESSES_DEFAULT: frozenset[str] = frozenset({
    "explorer.exe",
    "searchhost.exe",
    "searchapp.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
    "applicationframehost.exe",
})

# Live runtime variables — populated by _fetch_platform_db() on startup.
_PLATFORM_APP_MAP: dict[str, frozenset[str]] = {}
_BROWSER_PROCESSES: frozenset[str] = frozenset()
_TRANSIT_PROCESSES: frozenset[str] = frozenset()


def _fetch_platform_db() -> None:
    """Fetch platform mappings from the HopMap server (GET /api/platforms).

    Populates the module-level ``_PLATFORM_APP_MAP``, ``_BROWSER_PROCESSES``
    and ``_TRANSIT_PROCESSES`` from the server's centralised config.

    Falls back to the hardcoded defaults below if the server is unreachable,
    keeping the agent functional even when the network is temporarily down.
    """
    global _PLATFORM_APP_MAP, _BROWSER_PROCESSES, _TRANSIT_PROCESSES

    try:
        resp = requests.get(f"{config_manager.backend_url}/api/platforms", timeout=5)
        resp.raise_for_status()
        data = resp.json()

        raw_map: dict[str, list[str]] = data.get("platforms", {})
        browsers: list[str]           = data.get("browsers",  [])
        transit:  list[str]           = data.get("transit",   [])

        if not raw_map:
            raise ValueError("Server returned empty platform map.")

        _PLATFORM_APP_MAP  = {k: frozenset(v) for k, v in raw_map.items()}
        _BROWSER_PROCESSES = frozenset(browsers)
        _TRANSIT_PROCESSES = frozenset(transit)

        log.info(
            "Fetched %d platforms, %d browsers, %d transit processes from server.",
            len(_PLATFORM_APP_MAP), len(_BROWSER_PROCESSES), len(_TRANSIT_PROCESSES),
        )

    except (requests.exceptions.RequestException, ValueError, KeyError) as exc:
        log.warning(
            "Could not fetch platform config from server (%s) — using built-in defaults.",
            exc,
        )
        _use_builtin_platform_defaults()


def _use_builtin_platform_defaults() -> None:
    """Populate platform globals with hardcoded fallback values."""
    global _PLATFORM_APP_MAP, _BROWSER_PROCESSES, _TRANSIT_PROCESSES
    _PLATFORM_APP_MAP  = _PLATFORM_APP_MAP_DEFAULT
    _BROWSER_PROCESSES = _BROWSER_PROCESSES_DEFAULT
    _TRANSIT_PROCESSES = _TRANSIT_PROCESSES_DEFAULT
    log.info("Using built-in platform defaults.")


# ---------------------------------------------------------------------------
# Tesseract auto-detection  (used only by the local Ollama fallback path)
# ---------------------------------------------------------------------------

_TESSERACT_DEFAULT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _configure_tesseract() -> None:
    """Point pytesseract at the Tesseract binary if it is not already on PATH."""
    current = pytesseract.pytesseract.tesseract_cmd
    if current and current != "tesseract":
        return  # already configured explicitly
    if shutil.which("tesseract"):
        return  # found on PATH
    if pathlib.Path(_TESSERACT_DEFAULT_PATH).exists():
        pytesseract.pytesseract.tesseract_cmd = _TESSERACT_DEFAULT_PATH


_configure_tesseract()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BACKEND_URL = config_manager.backend_url
CHILD_ID: str = ""  # assigned by the server on startup
SCAN_INTERVAL = config_manager.scan_interval_seconds
CONTEXT_LINES = config_manager.context_lines

# File where the server-assigned child ID is persisted so the same record is
# reused across agent restarts rather than creating a new orphaned profile.
_CHILD_ID_FILE = pathlib.Path(__file__).parent / ".child_id"


def _register_child() -> str:
    """Return the persisted child ID, registering with the server if needed.

    The ID is written to *_CHILD_ID_FILE* so the same child record survives
    agent restarts — event history remains intact in the parent dashboard.
    """
    # ── Load a previously persisted ID ───────────────────────────────────
    try:
        if _CHILD_ID_FILE.exists():
            stored = _CHILD_ID_FILE.read_text(encoding="utf-8").strip()
            if stored:
                log.info("Using persisted child ID %r.", stored)
                # Notify the server we are back online; it ignores the call if
                # the child is already registered (upsert with $setOnInsert).
                try:
                    requests.post(
                        f"{BACKEND_URL}/api/children",
                        json={"childId": stored},
                        timeout=5,
                    )
                except requests.exceptions.RequestException:
                    pass  # offline — that's OK, we still know our ID
                return stored
    except OSError:
        pass

    # ── Register fresh with the server ───────────────────────────────────
    try:
        resp = requests.post(f"{BACKEND_URL}/api/children", json={}, timeout=5)
        resp.raise_for_status()
        assigned = resp.json()["childId"]
        log.info("Server assigned child ID %r.", assigned)
        try:
            _CHILD_ID_FILE.write_text(assigned, encoding="utf-8")
        except OSError as exc:
            log.warning("Could not persist child ID to disk: %s", exc)
        return assigned
    except requests.exceptions.RequestException as exc:
        log.warning("Could not reach server for registration: %s", exc)
        return "child-unknown"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Named logger with its own handler so that third-party libraries (httpx,
# urllib3, ollama) adding handlers to the root logger cannot produce duplicate
# lines in our output.

log = logging.getLogger("hopmap-agent")
log.setLevel(logging.DEBUG)
log.propagate = False

if not log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s  %(message)s", datefmt="%H:%M:%S"
        )
    )
    log.addHandler(_handler)

# ---------------------------------------------------------------------------
# Game-process registry
# ---------------------------------------------------------------------------
# Layer 1 — Windows Game Mode registry (dynamic, authoritative).
# Layer 2 — Launcher manifests: Epic Games + Riot Games (catches installs before first launch).
# Layer 3 — Hardcoded fallback (top games, covers Game Mode disabled edge case).

_GAME_PROCESSES_FALLBACK: frozenset[str] = frozenset({
    "robloxplayerbeta.exe", "roblox.exe",
    "minecraft.exe", "minecraftlauncher.exe",
    "javaw.exe",            # Minecraft Java Edition
    "fortnite.exe",
    "steam.exe", "steamwebhelper.exe",
    "leagueclient.exe", "league of legends.exe",
    "valorant.exe",
    "gta5.exe",
})

# Cache state — refreshed every _GAME_CACHE_TTL seconds.
_game_processes_cache:    frozenset[str] = frozenset()
_game_cache_updated_at:   float          = 0.0
_game_cache_lock:         threading.Lock = threading.Lock()
_GAME_CACHE_TTL:          float          = 60.0

# Base path for per-machine application data; respects %PROGRAMDATA% redirects.
_PROGRAMDATA = pathlib.Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))

# Epic Games manifest directory (Windows default).
_EPIC_MANIFESTS_DIR = _PROGRAMDATA / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"

# Riot Games metadata directory (Windows default).
# Each subdirectory is a product (e.g. live-valorant-win, live-league_of_legends-win)
# and contains a <product>.product_settings.yaml with an "exe_name" field.
_RIOT_METADATA_DIR = _PROGRAMDATA / "Riot Games" / "Metadata"


def _load_from_registry() -> set[str]:
    """Return exe basenames registered in the Windows Game Mode registry.

    Reads ``HKEY_CURRENT_USER\\System\\GameConfigStore\\Children``.  Each
    sub-key that has a ``MatchedExeFullPath`` value represents a game Windows
    has detected via DirectX/Vulkan/OpenGL initialisation.

    Returns an empty set silently when the key is absent (Game Mode disabled).
    """
    exes: set[str] = set()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"System\GameConfigStore\Children",
        ) as parent:
            index = 0
            while True:
                try:
                    child_name = winreg.EnumKey(parent, index)
                    index += 1
                except OSError:
                    break  # no more sub-keys
                try:
                    with winreg.OpenKey(parent, child_name) as child:
                        value, _ = winreg.QueryValueEx(child, "MatchedExeFullPath")
                        exes.add(pathlib.Path(value).name.lower())
                except OSError:
                    continue  # sub-key has no MatchedExeFullPath — skip
    except OSError:
        pass  # registry key absent — Game Mode disabled or unsupported OS
    return exes


def _load_from_epic() -> set[str]:
    """Return exe basenames from locally installed Epic Games titles.

    Scans ``*.item`` manifest files written by the Epic Games Launcher.  Each
    file is JSON and contains a ``LaunchExecutable`` field with a relative path
    to the game's main executable (e.g. ``"FortniteGame/Binaries/Win64/FortniteLauncher.exe"``).

    Returns an empty set silently when Epic is not installed.
    """
    exes: set[str] = set()
    try:
        for manifest in _EPIC_MANIFESTS_DIR.glob("*.item"):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                launch_exe = data.get("LaunchExecutable", "")
                if launch_exe:
                    exes.add(pathlib.Path(launch_exe).name.lower())
            except (json.JSONDecodeError, OSError, ValueError):
                continue  # malformed manifest — skip
    except OSError:
        pass  # Epic not installed
    return exes


def _load_from_riot() -> set[str]:
    """Return exe basenames from locally installed Riot Games titles.

    Scans ``_RIOT_METADATA_DIR`` for product subdirectories.  Each subdirectory
    contains a ``*.product_settings.yaml`` file with an ``exe_name`` field
    (e.g. ``"VALORANT-Win64-Shipping.exe"``).  The field is extracted with
    simple string matching to avoid a PyYAML dependency.

    Returns an empty set silently when Riot Games is not installed.
    """
    exes: set[str] = set()
    try:
        for product_dir in _RIOT_METADATA_DIR.iterdir():
            if not product_dir.is_dir():
                continue
            for settings_file in product_dir.glob("*.product_settings.yaml"):
                try:
                    content = settings_file.read_text(encoding="utf-8", errors="ignore")
                    for line in content.splitlines():
                        # Match lines like:  exe_name: "VALORANT-Win64-Shipping.exe"
                        stripped = line.strip()
                        if stripped.startswith("exe_name:"):
                            value = stripped.split(":", 1)[1].strip().strip('"\'')
                            if value:
                                exes.add(pathlib.Path(value).name.lower())
                except (OSError, ValueError):
                    continue
    except OSError:
        pass  # Riot Games not installed
    return exes


def _load_game_processes() -> frozenset[str]:
    """Union all three detection layers into a single frozenset of exe basenames."""
    return frozenset(
        _load_from_registry()
        | _load_from_epic()
        | _load_from_riot()
        | _GAME_PROCESSES_FALLBACK
    )


def _is_game(proc_name: str) -> bool:
    """Return True when *proc_name* belongs to a known game process.

    Uses a 60-second TTL cache so the registry and launcher manifests are not
    read on every foreground-change event, while still picking up newly
    installed or launched games without an agent restart.
    """
    global _game_processes_cache, _game_cache_updated_at

    now = time.monotonic()
    if now - _game_cache_updated_at > _GAME_CACHE_TTL:
        with _game_cache_lock:
            # Double-checked locking: another thread may have refreshed while
            # we were waiting to acquire the lock.
            if now - _game_cache_updated_at > _GAME_CACHE_TTL:
                _game_processes_cache  = _load_game_processes()
                _game_cache_updated_at = time.monotonic()
                log.debug(
                    "Game-process cache refreshed (%d entries).",
                    len(_game_processes_cache),
                )

    return proc_name.lower() in _game_processes_cache


# ---------------------------------------------------------------------------
# Platform → native-app mapping  (click-confidence tier 1)
# ---------------------------------------------------------------------------
# (Built-in defaults defined at the top of the Platform section above.)

# ---------------------------------------------------------------------------
# URL utilities
# ---------------------------------------------------------------------------

# Matches full https/http URLs and bare domain/path combos such as
# "discord.gg/abc" or "t.me/xyz".  Requiring at least one slash after the TLD
# prevents bare process names like "discord.exe" from matching.
_URL_RE = re.compile(
    r"https?://[^\s\"'<>]+"  # full https / http URL
    r"|[a-z0-9\-]+\.[a-z]{2,}/\S+",  # bare domain/path  e.g. discord.gg/abc
    re.IGNORECASE,
)
_URL_TRAILING_PUNCT = re.compile(r"[.,;:!?'\")<>]+$")


def _find_urls(text: str) -> list[str]:
    """Return every URL-like token in *text*, stripped of trailing punctuation."""
    return [_URL_TRAILING_PUNCT.sub("", u) for u in _URL_RE.findall(text)]


def _extract_domain(url: str) -> str:
    """Return the lowercase netloc of *url*, or the raw string for bare URLs."""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return parsed.netloc.lower() or url.lower()
    except Exception:
        return url.lower()


def _app_matches_url(url: str, proc: str) -> bool:
    """Return True when *proc* is the native desktop app for *url*'s platform."""
    domain = _extract_domain(url)
    for keyword, procs in _PLATFORM_APP_MAP.items():
        if keyword in domain:
            return proc.lower() in procs
    return False


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------


def _extract_context(text: str, url: str, n: int = CONTEXT_LINES) -> str:
    """Return up to *n* lines centred on the line that contains *url*."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if url in line:
            start = max(0, i - n // 2)
            end = min(len(lines), start + n)
            return "\n".join(lines[start:end])
    return url  # fallback: just the URL itself


# ---------------------------------------------------------------------------
# TTL de-duplication cache
# ---------------------------------------------------------------------------


class _TTLCache:
    """Bounded, time-expiring membership set.  Thread-safe.

    ``seen(key)`` returns True if *key* was recorded within *ttl_seconds* and
    has not yet expired.  Always records the key on first or post-expiry calls
    so the next call within the window returns True.
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 500) -> None:
        self._ttl = ttl_seconds
        self._max = max_size
        self._store: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    def seen(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._evict(now)
            if key in self._store:
                return True
            self._store[key] = now
            if len(self._store) > self._max:
                self._store.popitem(last=False)
            return False

    def _evict(self, now: float) -> None:
        cutoff = now - self._ttl
        while self._store:
            _, oldest_ts = next(iter(self._store.items()))
            if oldest_ts < cutoff:
                self._store.popitem(last=False)
            else:
                break


# Global URL dedup cache — shared by scanner + clipboard monitor.
# Prevents the same URL being re-classified (and re-confirmed) across
# scanner restarts and clipboard re-reads within the TTL window.
_url_seen_global: _TTLCache = _TTLCache(ttl_seconds=300)


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ClassifyResult:
    is_hop: bool
    confidence: int  # 0–100
    reason: str
    via: str  # "server" | "error"


# ---------------------------------------------------------------------------
# Classifier  (delegates entirely to the HopMap server)
# ---------------------------------------------------------------------------


def _classify(url: str, context: str, detection_source: str) -> _ClassifyResult:
    """POST a classify request to the HopMap server and return a structured result.

    If the server is unreachable the URL is treated as innocent (no false positives).

    Args:
        url:              The candidate URL extracted from chat or clipboard.
        context:          Surrounding chat lines sent as LLM context.
        detection_source: ``"ocr"`` or ``"clipboard"`` — logged server-side.
    """
    payload = {
        "childId": CHILD_ID,
        "url": url,
        "context": context,
        "source": detection_source,
    }

    try:
        resp = requests.post(
            f"{BACKEND_URL}/agent/classify",
            json=payload,
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        decision = str(data.get("decision", "NO")).upper()
        confidence = max(0, min(100, int(data.get("confidence", 0))))
        reason = str(data.get("reason", "")).strip()

        log.debug(
            "Classify → %s  %d%%  %r  (%s)",
            decision,
            confidence,
            reason,
            url,
        )
        return _ClassifyResult(decision.startswith("YES"), confidence, reason, "server")

    except requests.exceptions.RequestException as exc:
        log.warning("Server classify unreachable (%s) — skipping URL.", exc)
        return _ClassifyResult(False, 0, "server_unreachable", "error")


# ---------------------------------------------------------------------------
# Window helpers
# ---------------------------------------------------------------------------


def _resolve_window(hwnd: int) -> tuple[str, str]:
    """Return *(proc_name_lower, window_title)* for *hwnd*."""
    title = win32gui.GetWindowText(hwnd)
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid <= 0:
            raise ValueError(f"invalid pid {pid!r}")
        proc = psutil.Process(pid).name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError, ValueError):
        proc = "unknown.exe"
    return proc, title


def _hwnd_rect(hwnd: int) -> Optional[tuple[int, int, int, int]]:
    """Return *(left, top, width, height)* for *hwnd*, or ``None`` if minimised."""
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        w, h = right - left, bottom - top
        if w <= 0 or h <= 0:
            return None
        return left, top, w, h
    except Exception:
        return None


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------


def _ocr_window(hwnd: int) -> str:
    """Screenshot *hwnd* and return all Tesseract-extracted text."""
    region = _hwnd_rect(hwnd)
    if region is None:
        return ""
    left, top, w, h = region
    with mss.mss() as sct:
        raw = sct.grab({"left": left, "top": top, "width": w, "height": h})
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    return pytesseract.image_to_string(img)


# ---------------------------------------------------------------------------
# Backend HTTP sender
# ---------------------------------------------------------------------------
# All outbound HTTP is performed on a single dedicated daemon thread so that
# no other code path (ctypes callbacks, scanner threads, classify threads)
# can ever block on network I/O.

_send_queue: queue.Queue[Optional[dict]] = queue.Queue()


def _sender_loop() -> None:
    """Drain *_send_queue* and POST each hop event to the backend."""
    while True:
        event = _send_queue.get()
        if event is None:  # shutdown sentinel
            return
        try:
            resp = requests.post(
                f"{BACKEND_URL}/agent/hop/{CHILD_ID}",
                json=event,
                timeout=5,
            )
            resp.raise_for_status()
            log.debug("Event sent to server.")
        except requests.exceptions.RequestException as exc:
            log.warning("Could not reach backend: %s", exc)


def _enqueue_hop(event: dict) -> None:
    """Enqueue *event* for non-blocking background delivery to the backend."""
    _send_queue.put(event)


# ---------------------------------------------------------------------------
# Pending-hop store
# ---------------------------------------------------------------------------
# Keyed by URL so that simultaneous lures from different links are tracked
# independently.  All mutations must be performed while holding *_pending_lock*.

_pending_lock = threading.Lock()
_pending_hop_attempts: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Last non-game switch recorder
# ---------------------------------------------------------------------------
# Stores the most recent foreground switch FROM a game TO a non-game,
# non-transit process.  Written by _process_foreground_change (event-processor
# thread) and read by _try_late_confirm (classify-dispatch threads).
#
# This closes the race where the child clicks a lure link BEFORE the server
# returns its classification result:
#
#   t=0s  URL detected, classify thread starts (network round-trip begins)
#   t=1s  Kid clicks the link → discord.exe comes to foreground
#   t=1s  _process_foreground_change fires → _pending_hop_attempts is still
#          empty (LLM hasn't replied yet) → records switch here instead
#   t=3s  LLM returns YES → pending parked → _try_late_confirm reads the
#          recorded switch and confirms the hop correctly
#
# All mutations must be performed while holding *_last_switch_lock*.

_last_switch_lock = threading.Lock()
_last_non_game_switch: Optional[dict] = None  # { proc, title, hwnd, at }

# Maximum age (seconds) of a recorded switch that _try_late_confirm will
# still act on.  Prevents a switch from many minutes ago being incorrectly
# attributed to a freshly classified lure.
_LATE_CONFIRM_MAX_AGE = 60.0

# ---------------------------------------------------------------------------
# Current-game state  (shared between event-processor and clipboard monitor)
# ---------------------------------------------------------------------------
# Set to (proc, title) while a game owns the foreground; None otherwise.
# Written exclusively by _process_foreground_change (event-processor thread).
# Read by _clipboard_monitor_loop — a plain assignment is GIL-safe.

_current_game: Optional[tuple[str, str]] = None

# ---------------------------------------------------------------------------
# Click-confidence: browser title poll  (tier 2)
# ---------------------------------------------------------------------------


def _poll_browser_title(
    hwnd: int,
    domain: str,
    event: dict,
    timeout: float = 10.0,
    interval: float = 0.5,
) -> None:
    """Poll the browser window title for *domain*; fire _enqueue_hop when found.

    Runs on a short-lived daemon thread so the event-processor is never blocked.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            title = win32gui.GetWindowText(hwnd)
        except Exception:
            break
        if domain in title.lower():
            log.warning("✓ HOP CONFIRMED  — browser reached %r", domain)
            _enqueue_hop({**event, "clickConfidence": "title_match"})
            return
        time.sleep(interval)

    log.debug("Browser title poll timed out — no exact match for %r.", domain)
    log.warning("✓ HOP CONFIRMED  — browser opened after suspicious link")
    _enqueue_hop({**event, "clickConfidence": "browser_switch"})


# ---------------------------------------------------------------------------
# Hop confirmation
# ---------------------------------------------------------------------------


def _confirm_pending(
    pending: dict,
    proc: str,
    title: str,
    hwnd: int,
) -> None:
    """Apply click-confidence logic and dispatch the confirmed hop event."""
    lure_url = pending["to"]
    base_event = {
        **pending,
        "confirmedTo": proc,
        "confirmedToTitle": title,
        "confirmedAt": datetime.now(tz=timezone.utc).isoformat(),
    }

    if _app_matches_url(lure_url, proc):
        log.warning("✓ HOP CONFIRMED  — %r opened (matches lure)", proc)
        _enqueue_hop({**base_event, "clickConfidence": "app_match"})

    elif proc in _BROWSER_PROCESSES:
        domain = _extract_domain(lure_url)
        log.debug("Waiting for browser to navigate to %r …", domain)
        threading.Thread(
            target=_poll_browser_title,
            args=(hwnd, domain, base_event),
            daemon=True,
            name="browser-title-poll",
        ).start()

    else:
        log.debug("App switch only — no strong confirmation.")
        _enqueue_hop({**base_event, "clickConfidence": "switch_only"})


# ---------------------------------------------------------------------------
# Late-confirm helper
# ---------------------------------------------------------------------------


def _drain_and_confirm(proc: str, title: str, hwnd: int) -> None:
    """Atomically drain *_pending_hop_attempts* and confirm each lure against
    the given destination.  Safe to call from any thread."""
    with _pending_lock:
        if not _pending_hop_attempts:
            return
        snapshot = dict(_pending_hop_attempts)
        _pending_hop_attempts.clear()

    for pending in snapshot.values():
        _confirm_pending(pending, proc, title, hwnd)


def _is_hop_destination(proc: str) -> bool:
    """Return True if *proc* is plausible as a hop destination.

    Only browsers and known platform desktop apps count — tools like MongoDB
    Compass, VS Code, or File Explorer should never trigger a false confirmation.
    """
    if proc in _BROWSER_PROCESSES:
        return True
    for procs in _PLATFORM_APP_MAP.values():
        if proc in procs:
            return True
    return False


def _try_late_confirm(game_proc: str) -> None:
    """Called immediately after parking a lure in *_pending_hop_attempts*.

    Handles the race where the child clicks a lure link BEFORE the server
    finishes classifying it.  Two checks are performed in order:

    Check 1 — current foreground.
        If the child is already on a non-game app right now, confirm
        immediately without waiting for the next foreground-change event.

    Check 2 — recorded switch.
        If the current foreground is still the game (or a transit process),
        look at the most recent non-game switch recorded by
        _process_foreground_change.  If it happened recently enough
        (_LATE_CONFIRM_MAX_AGE seconds) it means the child switched away
        while the server was classifying and already switched back (e.g.
        opened Discord briefly then alt-tabbed back).  We still confirm
        the hop against that recorded destination.
    """
    # Check 1 — prefer the recorded switch: it captures where the child
    # *actually* went, not just wherever they happen to be right now (which
    # may be a completely unrelated app they opened after Discord).
    with _last_switch_lock:
        last = _last_non_game_switch

    age = time.monotonic() - last["at"] if last else float("inf")

    if last and age <= _LATE_CONFIRM_MAX_AGE and _is_hop_destination(last["proc"]):
        log.warning(
            "CONFIRMED hop (late, switch to %r happened %.1fs ago).",
            last["proc"],
            age,
        )
        _drain_and_confirm(last["proc"], last["title"], last["hwnd"])
        return

    # Check 2 — fallback: child is still somewhere non-game right now.
    hwnd = win32gui.GetForegroundWindow()
    current_proc, current_title = _resolve_window(hwnd)

    if (
        not _is_game(current_proc)
        and current_proc not in _TRANSIT_PROCESSES
        and current_proc != game_proc
        and _is_hop_destination(current_proc)
    ):
        log.warning(
            "CONFIRMED hop (late, child currently at %r).",
            current_proc,
        )
        _drain_and_confirm(current_proc, current_title, hwnd)


# ---------------------------------------------------------------------------
# Classify-and-park dispatcher
# ---------------------------------------------------------------------------


def _decide_and_send(
    url: str,
    context: str,
    game_proc: str,
    game_title: str,
    detection_source: str,
) -> None:
    """Classify *url* via the server (or fallback); park a pending hop on YES.

    Always runs on its own short-lived daemon thread so the scanner loop and
    clipboard monitor keep ticking while we wait for the network round-trip.
    """
    result = _classify(url, context, detection_source)

    if not result.is_hop:
        log.debug(
            "Safe  %d%%  %r  (%s).",
            result.confidence,
            result.reason,
            url,
        )
        return

    log.warning(
        "⚠ Hop attempt  %r  — %s (%d%% confidence).  Watching for app switch…",
        url,
        result.reason,
        result.confidence,
    )

    pending: dict = {
        "from": game_proc,
        "to": url,
        "fromTitle": game_title,
        "toTitle": f"[link] {url}",
        "context": context,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "detection": "confirmed_hop",
        "classifyConfidence": result.confidence,
        "classifyReason": result.reason,
        "classifySource": result.via,
    }

    with _pending_lock:
        _pending_hop_attempts[url] = pending

    _try_late_confirm(game_proc)


# ---------------------------------------------------------------------------
# Game window scanner
# ---------------------------------------------------------------------------

_current_scanner_stop: Optional[threading.Event] = None


def _scanner_loop(
    hwnd: int,
    game_proc: str,
    game_title: str,
    stop: threading.Event,
) -> None:
    """Periodically OCR the game window and classify every new URL found."""
    log.info("Monitoring game: %s", game_proc)

    while not stop.is_set():
        try:
            text = _ocr_window(hwnd)
        except pytesseract.TesseractNotFoundError:
            log.error(
                "Tesseract binary not found.  "
                "Install from https://github.com/UB-Mannheim/tesseract/wiki "
                "and restart the agent."
            )
            return  # No point retrying on every tick.
        except Exception as exc:
            log.warning("OCR error: %s", exc)
            stop.wait(SCAN_INTERVAL)
            continue

        for url in _find_urls(text):
            if _url_seen_global.seen(url):
                continue

            context = _extract_context(text, url)
            log.info("Link detected: %s", url)

            threading.Thread(
                target=_decide_and_send,
                args=(url, context, game_proc, game_title, "ocr"),
                daemon=True,
                name="classify-dispatch",
            ).start()

        stop.wait(SCAN_INTERVAL)

    log.info("Stopped monitoring: %s", game_proc)


# ---------------------------------------------------------------------------
# Clipboard monitor
# ---------------------------------------------------------------------------


def _clipboard_monitor_loop(stop: threading.Event) -> None:
    """Poll the system clipboard every second for hop-luring URLs.

    Only classifies URLs while a game is in the foreground.  This prevents
    spurious alerts when the child (or anyone else) copies an innocent link
    while outside a game session.
    """
    last_content = ""

    while not stop.is_set():
        # Only act while a game is active.
        game = _current_game
        if game is None:
            last_content = ""
            stop.wait(1.0)
            continue

        game_proc, game_title = game

        try:
            current = pyperclip.paste()
        except Exception as exc:
            log.debug("Clipboard read error: %s", exc)
            stop.wait(1.0)
            continue

        if current != last_content:
            last_content = current
            for url in _find_urls(current):
                if _url_seen_global.seen(url):
                    continue
                log.info("Link in clipboard: %s", url)
                threading.Thread(
                    target=_decide_and_send,
                    args=(
                        url,
                        f"[clipboard] {url}",
                        game_proc,
                        game_title,
                        "clipboard",
                    ),
                    daemon=True,
                    name="classify-dispatch",
                ).start()

        stop.wait(1.0)


# ---------------------------------------------------------------------------
# Win32 foreground-event hook
# ---------------------------------------------------------------------------

_user32 = ctypes.windll.user32

EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000

_WinEventProc = ctypes.WINFUNCTYPE(
    None,
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HWND,
    ctypes.wintypes.LONG,
    ctypes.wintypes.LONG,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
)

# ---------------------------------------------------------------------------
# HWND event queue  (decouples the ctypes callback from all business logic)
# ---------------------------------------------------------------------------
# The Win32 callback must return as quickly as possible.  If it blocks,
# Windows can coalesce or drop subsequent foreground-change events.  We
# therefore do nothing in the callback except push the HWND onto a queue
# and let the dedicated event-processor thread handle everything else.

_hwnd_event_queue: queue.Queue[Optional[int]] = queue.Queue()


def _on_foreground_change(
    hWinEventHook,  # noqa: N803  — Win32 naming convention
    event,
    hwnd,
    idObject,  # noqa: N803
    idChild,  # noqa: N803
    dwEventThread,  # noqa: N803
    dwmsEventTime,  # noqa: N803
) -> None:
    """Win32 event callback — MUST return immediately.  Enqueues HWND only."""
    if hwnd:
        _hwnd_event_queue.put(hwnd)


# ---------------------------------------------------------------------------
# Event processor
# ---------------------------------------------------------------------------

_prev_proc: str = ""
_prev_title: str = ""
_scanner_thread: Optional[threading.Thread] = None


def _process_foreground_change(hwnd: int) -> None:
    """Handle a single foreground-window change event.

    Called exclusively by _event_processor_loop so it always runs on the same
    thread — no additional locking is needed for the module-level _prev_proc /
    _prev_title / scanner state.
    """
    global \
        _prev_proc, \
        _prev_title, \
        _scanner_thread, \
        _current_scanner_stop, \
        _current_game, \
        _last_non_game_switch

    proc, title = _resolve_window(hwnd)
    if proc == _prev_proc:
        return  # same process — nothing to do

    log.debug(
        "App switch: %s → %s",
        _prev_proc,
        proc,
    )

    # ------------------------------------------------------------------
    # Confirm any pending hop attempts (skip transient shell processes)
    # ------------------------------------------------------------------
    if proc not in _TRANSIT_PROCESSES:
        with _pending_lock:
            snapshot = dict(_pending_hop_attempts)
            _pending_hop_attempts.clear()

        if snapshot:
            if _is_game(proc):
                # The child came back to a game — treat all pending as false alarms.
                log.info("Pending hop(s) cleared — child returned to a game.")
            else:
                for pending in snapshot.values():
                    _confirm_pending(pending, proc, title, hwnd)

    # ------------------------------------------------------------------
    # Record this switch so _try_late_confirm can replay it if a lure
    # lands AFTER the child has already switched away.
    # Only non-game, non-transit destinations are worth recording.
    # ------------------------------------------------------------------
    if not _is_game(proc) and proc not in _TRANSIT_PROCESSES:
        with _last_switch_lock:
            _last_non_game_switch = {
                "proc": proc,
                "title": title,
                "hwnd": hwnd,
                "at": time.monotonic(),
            }

    # ------------------------------------------------------------------
    # Stop any running game scanner
    # ------------------------------------------------------------------
    if _scanner_thread and _scanner_thread.is_alive():
        if _current_scanner_stop is not None:
            _current_scanner_stop.set()
        # Do not join here — we are on the event-processor thread and joining
        # would block processing of all subsequent foreground events.

    # ------------------------------------------------------------------
    # Start a new scanner on game entry; record a plain hop otherwise
    # ------------------------------------------------------------------
    if _is_game(proc):
        _current_game = (proc, title)  # clipboard monitor may now classify
        stop = threading.Event()
        _current_scanner_stop = stop
        _scanner_thread = threading.Thread(
            target=_scanner_loop,
            args=(hwnd, proc, title, stop),
            daemon=True,
            name="game-scanner",
        )
        _scanner_thread.start()
    else:
        _current_game = None  # clipboard monitor stops classifying
        # Skip transit shells — they are intermediate steps, not real
        # destinations, and posting them is pure noise.
        # Only report this plain switch when leaving a game.
        # Non-game-to-non-game switches (e.g. discord → code) are noise.
        if proc not in _TRANSIT_PROCESSES and _is_game(_prev_proc):
            _enqueue_hop(
                {
                    "from": _prev_proc,
                    "to": proc,
                    "fromTitle": _prev_title,
                    "toTitle": title,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "detection": "foreground_hook",
                }
            )

    _prev_proc = proc
    _prev_title = title


def _event_processor_loop() -> None:
    """Drain *_hwnd_event_queue* and dispatch each HWND to the handler."""
    while True:
        hwnd = _hwnd_event_queue.get()
        if hwnd is None:  # shutdown sentinel
            return
        try:
            _process_foreground_change(hwnd)
        except Exception as exc:
            log.exception("Unhandled error in event processor: %s", exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run() -> None:
    """Start all background threads, register the Win32 hook, and pump the
    Windows message loop until Ctrl-C is pressed."""
    global _prev_proc, _prev_title, _current_scanner_stop, _current_game

    # Fetch platform mappings from the server (falls back to built-in defaults
    # if the server is unreachable — agent still starts normally either way).
    _fetch_platform_db()

    initial_hwnd = win32gui.GetForegroundWindow()
    _prev_proc, _prev_title = _resolve_window(initial_hwnd)

    # ── Background threads ────────────────────────────────────────────────
    threading.Thread(target=_sender_loop, daemon=True, name="hop-sender").start()
    threading.Thread(
        target=_event_processor_loop, daemon=True, name="event-processor"
    ).start()

    clipboard_stop = threading.Event()
    threading.Thread(
        target=_clipboard_monitor_loop,
        args=(clipboard_stop,),
        daemon=True,
        name="clipboard-monitor",
    ).start()

    # ── Win32 event hook ──────────────────────────────────────────────────
    hook_proc = _WinEventProc(_on_foreground_change)
    hook = _user32.SetWinEventHook(
        EVENT_SYSTEM_FOREGROUND,
        EVENT_SYSTEM_FOREGROUND,
        0,
        hook_proc,
        0,
        0,
        WINEVENT_OUTOFCONTEXT,
    )
    if not hook:
        log.error("SetWinEventHook failed — aborting.")
        return

    # Register with the server; use the ID it returns (may be server-generated).
    global CHILD_ID
    CHILD_ID = _register_child()

    log.info(
        "HopMap agent running. Current app: %s. Press Ctrl-C to stop.",
        _prev_proc,
    )

    # If the agent launched while a game was already in the foreground, start
    # the scanner immediately without waiting for a foreground-change event.
    if _is_game(_prev_proc):
        _current_game = (_prev_proc, _prev_title)
        stop = threading.Event()
        _current_scanner_stop = stop
        threading.Thread(
            target=_scanner_loop,
            args=(initial_hwnd, _prev_proc, _prev_title, stop),
            daemon=True,
            name="game-scanner",
        ).start()

    # ── Windows message loop ──────────────────────────────────────────────
    # PeekMessageW + a 100 ms sleep keeps CPU usage near zero while allowing
    # the Win32 hook to fire reliably for every foreground change.
    msg = ctypes.wintypes.MSG()
    PM_REMOVE = 0x0001

    try:
        while True:
            while _user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, PM_REMOVE):
                _user32.TranslateMessage(ctypes.byref(msg))
                _user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.1)
    except KeyboardInterrupt:
        log.info("Shutdown requested — goodbye.")
    finally:
        if _current_scanner_stop is not None:
            _current_scanner_stop.set()
        clipboard_stop.set()
        _user32.UnhookWinEvent(hook)
        _send_queue.put(None)  # hop-sender sentinel
        _hwnd_event_queue.put(None)  # event-processor sentinel


if __name__ == "__main__":
    run()
