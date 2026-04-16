"""
HopMap Server.

Responsibilities
────────────────
  • Receive hop events from desktop agents  (POST /agent/hop/{child_id})
  • Classify raw URL + context snippets with a server-side LLM
                                            (POST /agent/classify)
  • Persist alert events to the database
  • Stream live events to parent dashboards via SSE  (GET /stream/{child_id})
  • Expose REST endpoints for event history, settings, whitelist, blacklist

Classification approach
───────────────────────
  The /agent/classify endpoint runs Ollama locally on the server, keeping all
  LLM inference off the child's gaming machine.  The agent sends only a small
  context snippet (a few lines of chat + the detected URL), so the payload is
  minimal and latency is dominated by the model inference time, not the network.

  The prompt catches explicit links, bare platform usernames, and
  invitation-style phrasing ("DM me on insta") — not just raw URLs.

  A per-child async rate limiter prevents a misbehaving agent from flooding
  the classifier.

Required packages (pip install):
    fastapi  uvicorn[standard]  ollama  python-dotenv

Run with:
    uvicorn server:app --host 0.0.0.0 --port 8000
    # or directly:
    python server.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

import db
from config import config_manager
from llm import LLMProvider, get_provider
from words_filter import WordsFilter

# ---------------------------------------------------------------------------
# Nasty Words Database (Excel-based word blocking)
# ---------------------------------------------------------------------------
# Blocked words — in-memory cache, source of truth is MongoDB `words` collection.
# Seeded once from Excel on first startup. Refreshed on a TTL background task
# and immediately after any write via the /api/words endpoints.

_filter: WordsFilter = WordsFilter()   # Aho-Corasick multi-pattern filter
_words_refresh_task: asyncio.Task | None = None

# ---------------------------------------------------------------------------
# Platform Database (Excel-based, served to agents via GET /api/platforms)
# ---------------------------------------------------------------------------

_platform_app_map: dict[str, list[str]] = {}
_browser_processes: list[str] = []
_transit_processes: list[str] = []


def _load_platforms_db() -> None:
    """Load platform→process mappings from the Excel file at startup.

    Expected columns: ``platform`` and ``process``.
    Special platform names ``browser`` and ``transit`` populate the
    corresponding process lists rather than the platform map.

    If the file is absent or malformed, the module-level lists remain empty
    and the server still starts — agents will fall back to their hardcoded
    defaults.
    """
    import openpyxl

    excel_path = config_manager.data.platforms_db_path
    if not excel_path or not os.path.exists(excel_path):
        log.warning("Platforms DB not found at %r — agents will use built-in defaults.", excel_path)
        return

    try:
        workbook  = openpyxl.load_workbook(excel_path, read_only=True)
        try:
            worksheet = workbook.active

            platform_col = process_col = None
            for cell in worksheet[1]:
                if cell.value:
                    name = str(cell.value).strip().lower()
                    if name == "platform":
                        platform_col = cell.column - 1
                    elif name == "process":
                        process_col = cell.column - 1

            if platform_col is None or process_col is None:
                log.warning("Platforms DB missing 'platform' or 'process' column — skipping.")
                return

            platforms: dict[str, set[str]] = {}
            browsers:  set[str] = set()
            transits:  set[str] = set()

            for row in worksheet.iter_rows(min_row=2, values_only=True):
                if not row:
                    continue
                plat = row[platform_col] if platform_col < len(row) else None
                proc = row[process_col]  if process_col  < len(row) else None
                if not plat or not proc:
                    continue
                plat = str(plat).strip().lower()
                proc = str(proc).strip().lower()
                if not plat or not proc:
                    continue
                if plat == "browser":
                    browsers.add(proc)
                elif plat == "transit":
                    transits.add(proc)
                else:
                    platforms.setdefault(plat, set()).add(proc)
        finally:
            workbook.close()

        global _platform_app_map, _browser_processes, _transit_processes
        _platform_app_map  = {k: sorted(v) for k, v in platforms.items()}
        _browser_processes = sorted(browsers)
        _transit_processes = sorted(transits)

        log.info(
            "Loaded %d platforms, %d browsers, %d transit processes from %s",
            len(_platform_app_map), len(_browser_processes), len(_transit_processes),
            excel_path,
        )

    except Exception as exc:
        log.warning("Failed to load platforms DB: %s — agents will use built-in defaults.", exc)
        _platform_app_map.clear()
        _browser_processes.clear()
        _transit_processes.clear()


def _load_blocked_words() -> None:
    """Reload the in-memory blocked-words filter from MongoDB.

    Builds a fresh Aho-Corasick automaton from the full entry list so that
    all patterns — including special-char entries like '18+' and non-ASCII
    scripts like Hebrew — are matched correctly.

    Called once during startup, periodically by the background refresh task,
    and immediately after any write via the /api/words endpoints.
    """
    try:
        entries = db.get_blocked_words()
        _filter.build(entries)
        log.info(
            "Blocked entries reloaded: %d total (%d single-word, %d phrase)",
            _filter.entry_count,
            len(_filter.words),
            _filter.entry_count - len(_filter.words),
        )
    except Exception as exc:
        log.warning("Failed to reload blocked words from MongoDB: %s", exc)


async def _words_refresh_loop() -> None:
    """Background asyncio task: reload blocked words every N seconds."""
    interval = config_manager.db.words_refresh_interval_seconds
    while True:
        await asyncio.sleep(interval)
        _load_blocked_words()


def check_blocked_words(text: str) -> tuple[bool, str]:
    """Check if any blocked word or phrase appears in the given text.

    Delegates to the module-level :data:`_filter` (Aho-Corasick automaton).
    Returns ``(True, matched_entry)`` on the first (longest) match, or
    ``(False, "")`` when no blocked entry is found.
    """
    found, matched = _filter.find(text)
    if found:
        log.info("Blocked entry detected: '%s'", matched)
    return found, matched


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("hopmap-server")

# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _words_refresh_task
    log.info("HopMap server starting.")
    db.initialize_indexes()

    # Seed MongoDB words collection from Excel on first run (empty collection only).
    words_path = config_manager.data.words_db_path
    if not db.get_blocked_words() and words_path and os.path.exists(words_path):
        seeded = db.seed_words_from_excel(words_path)
        log.info("Seeded %d words from Excel into MongoDB words collection", seeded)

    # Load blocked words into memory and start background refresh task.
    _load_blocked_words()
    _words_refresh_task = asyncio.create_task(_words_refresh_loop())

    # Load platform→process mappings (served to agents via GET /api/platforms)
    _load_platforms_db()

    yield

    log.info("HopMap server shutting down.")
    if _words_refresh_task is not None:
        _words_refresh_task.cancel()
        await asyncio.gather(_words_refresh_task, return_exceptions=True)
    # Signal all open SSE generators to exit before Uvicorn's cancel deadline.
    for queues in list(_sse_queues.values()):
        for q in queues:
            await q.put(_SSE_SHUTDOWN)


app = FastAPI(title="HopMap API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config_manager.network.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Per-child SSE queues
# ---------------------------------------------------------------------------
# Each connected dashboard tab registers its own asyncio.Queue here.
# Structure: { child_id: [Queue, Queue, …] }

_sse_queues: dict[str, list[asyncio.Queue]] = {}
_SSE_SHUTDOWN = object()  # sentinel injected into queues on server shutdown

# Whether demo/seeding endpoints are exposed (set DEMO_MODE=true in .env)
_DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"

# ---------------------------------------------------------------------------
# LLM provider singleton
# ---------------------------------------------------------------------------
# Created once at startup from the LLM_PROVIDER + OLLAMA_MODEL env-vars.
# To swap providers, change LLM_PROVIDER in .env — no code changes needed.

_llm: LLMProvider = get_provider(
    name=config_manager.llm.provider,
    model=config_manager.llm.model,
)

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

_CHILD_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def _validate_child_id(child_id: str) -> None:
    """Raise HTTP 400 if *child_id* contains invalid characters."""
    if not _CHILD_ID_RE.match(child_id):
        raise HTTPException(status_code=400, detail="Invalid childId format.")


async def _broadcast(child_id: str, payload: dict) -> None:
    """Push *payload* to every SSE queue registered for *child_id*."""
    for q in _sse_queues.get(child_id, []):
        await q.put(payload)


# ---------------------------------------------------------------------------
# Server-side classifier
# ---------------------------------------------------------------------------
# The LLM runs here, not on the child's machine.  The agent sends only a small
# context snippet; we return a structured JSON decision.

_CLASSIFY_SYSTEM_PROMPT = """\
You are a child-safety monitor reviewing in-game chat messages for predatory behavior, hate speech, and inappropriate content.

Reply YES if the message contains ANY of the following:
 - OFF-PLATFORMING: Links or handles for Discord, Telegram, Snap, Instagram, WhatsApp, TikTok, etc.; requests to "move to DMs", "friend me on Discord", "join my server", "add me on [platform]", or "voice chat elsewhere."
 - FREE-ITEM LURE: Promises of free Robux, skins, items, or in-game currency contingent on joining an external platform or clicking a link.
 - HATE SPEECH / ANTISEMITISM: Any slur, dehumanizing language, or tropes targeting Jewish people or any other protected group (race, religion, gender, identity).
 - SEXUAL CONTENT: Explicit language, requests for ERP (Erotic Roleplay), sexualized comments about avatars, or requests for photos.
 - GROOMING / INTRUSIVE QUESTIONS: Asking for age, real-world location (city, school, country), phone number, or whether the child is alone at home.

Reply NO if:
 - The link is an official game resource (wiki, patch notes, Roblox Help Center, Minecraft.net, Steam store page).
 - The chat is strictly about gameplay, strategy, or in-game item trading with no external-platform element.
 - The language is competitive (trash talk) but contains no slurs and no predatory intent.

Respond with a JSON object ONLY — no markdown, no explanation, no extra text.
Schema:
{
  "decision":   "YES" or "NO",
  "confidence": integer 0-100,
  "reason":     "one short phrase describing the violation (max 10 words)"
}
"""

# Maximum classify calls per child per minute.
_CLASSIFY_MAX_RPM = 30

# { child_id: [monotonic_timestamp, …] }  — evicted lazily on each request.
_classify_call_times: dict[str, list[float]] = {}
_classify_rate_lock = asyncio.Lock()


async def _check_classify_rate_limit(child_id: str) -> bool:
    """Return True if the request is within the allowed rate, False otherwise."""
    now = time.monotonic()
    async with _classify_rate_lock:
        # Rebuild the window, evicting timestamps older than 60 s.  Storing
        # only the trimmed list prevents the dict from growing unbounded.
        recent = [t for t in _classify_call_times.get(child_id, []) if now - t < 60.0]
        if len(recent) >= _CLASSIFY_MAX_RPM:
            _classify_call_times[child_id] = recent
            return False
        recent.append(now)
        _classify_call_times[child_id] = recent
        return True


def _run_llm_classify(context: str) -> dict:
    """Delegate inference to the configured LLM provider (synchronous).

    Intended to be called via asyncio.to_thread so the event loop is never
    blocked during inference.

    Raises:
        json.JSONDecodeError: if the model response cannot be parsed as JSON.
        Exception:           for any provider-level failure (network, auth, etc.).
    """
    return _llm.classify(context, _CLASSIFY_SYSTEM_PROMPT)


class ClassifyRequest(BaseModel):
    child_id: str = Field(..., alias="childId")
    url: str
    context: str
    source: str = "unknown"  # "ocr" | "clipboard" | "unknown"

    model_config = {"populate_by_name": True}


class ClassifyResponse(BaseModel):
    decision: str  # "YES" | "NO"
    confidence: int  # 0–100
    reason: str
    via: str = "server"


@app.post("/agent/classify", response_model=ClassifyResponse)
async def agent_classify(body: ClassifyRequest) -> ClassifyResponse:
    """Classify a URL + context snippet with the configured LLM provider.

    Called by the desktop agent for every new URL it detects.  The agent sends
    only a few lines of chat context so the payload is small.  Inference is the
    dominant latency — typically 1–4 s on a CPU with a 7B model.

    Flow:
        1. Check if any blocked word from the Excel database appears in context
           → If found: return YES immediately (no LLM call needed)
        2. Otherwise: call LLM for deeper analysis

    Returns HTTP 429 if the per-child rate limit is exceeded.
    Returns decision="NO", confidence=0 on any inference error so the agent
    treats the result as a non-event rather than a false positive.
    """
    _validate_child_id(body.child_id)
    if not await _check_classify_rate_limit(body.child_id):
        log.warning("Classify rate limit hit  child=%r — rejecting.", body.child_id)
        raise HTTPException(
            status_code=429,
            detail="Classification rate limit exceeded.",
        )

    log.info(
        "Classifying  child=%r  source=%r  url=%s",
        body.child_id,
        body.source,
        body.url,
    )

    # -----------------------------------------------------------------------
    # STEP 1: Fast word matching BEFORE calling LLM
    # -----------------------------------------------------------------------
    # Check if any blocked word from the Excel DB appears in the message.
    # This is a simple O(n) string match - much faster than LLM inference.
    # If a word is found, we alert immediately without LLM.

    word_found, matched_word = check_blocked_words(body.context)
    if word_found:
        # Blocked word detected - return YES immediately, no LLM needed
        log.info(
            "Blocked word matched for child=%r word=%r - skipping LLM",
            body.child_id,
            matched_word,
        )
        return ClassifyResponse(
            decision="YES",
            confidence=100,  # Maximum confidence for direct word match
            reason=f"blocked_word: {matched_word}",
            via="word_db",  # Indicates this came from word matching, not LLM
        )

    # -----------------------------------------------------------------------
    # STEP 2: LLM classification (fallback when no blocked words found)
    # -----------------------------------------------------------------------
    # No blocked words matched - now use LLM for deeper analysis

    try:
        result = await asyncio.to_thread(_run_llm_classify, body.context)
    except json.JSONDecodeError as exc:
        log.warning("LLM returned non-JSON for child %r: %s", body.child_id, exc)
        return ClassifyResponse(decision="NO", confidence=0, reason="parse_error")
    except Exception as exc:
        log.warning("LLM error for child %r: %s", body.child_id, exc)
        return ClassifyResponse(decision="NO", confidence=0, reason="inference_error")

    log.info(
        "Classify result  child=%r  decision=%s  confidence=%d%%  reason=%r",
        body.child_id,
        result["decision"],
        result["confidence"],
        result["reason"],
    )
    # Add via="server" to indicate this came from LLM (not word_db)
    result["via"] = "server"
    return ClassifyResponse(**result)


# ---------------------------------------------------------------------------
# Hop event ingestion
# ---------------------------------------------------------------------------


@app.post("/agent/hop/{child_id}")
async def agent_hop(child_id: str, request: Request) -> dict:
    """Desktop agent POSTs app-switch events here."""
    _validate_child_id(child_id)
    body = await request.json()

    alert_reason: Optional[str] = (
        "confirmed_hop" if body.get("detection") == "confirmed_hop" else None
    )

    event = {
        "childId": child_id,
        "source": "desktop",
        "from": body.get("from", ""),
        "to": body.get("to", ""),
        "fromTitle": body.get("fromTitle", ""),
        "toTitle": body.get("toTitle", ""),
        "timestamp": body.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "blocked": False,
        "alert": alert_reason is not None,
        "alertReason": alert_reason,
        "receivedAt": datetime.now(timezone.utc).isoformat(),
        "clickConfidence": body.get("clickConfidence"),
        "confirmedTo": body.get("confirmedTo"),
        "confirmedToTitle": body.get("confirmedToTitle"),
        "confirmedAt": body.get("confirmedAt"),
        "context": body.get("context"),
        "classifyConfidence": body.get("classifyConfidence"),
        "classifyReason": body.get("classifyReason"),
        "classifySource": body.get("classifySource"),
    }

    if alert_reason is not None and body.get("clickConfidence") != "switch_only":
        db.insert_event(event)
    await _broadcast(child_id, {"type": "event", **event})

    log.info(
        "Hop  %r → %r  (%r → %r)  alert=%s",
        event["from"],
        event["to"],
        event["fromTitle"],
        event["toTitle"],
        alert_reason or "none",
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# SSE stream  (parent dashboard)
# ---------------------------------------------------------------------------


@app.get("/stream/{child_id}")
async def stream(child_id: str, request: Request) -> StreamingResponse:
    """
    Parent dashboard connects here via EventSource.

    On connect: immediately streams the full event history so the dashboard
    renders past events without a separate HTTP request.
    Thereafter: streams live events as they arrive.
    Auto-reconnects for free — the browser's EventSource handles it.
    """
    _validate_child_id(child_id)
    q: asyncio.Queue = asyncio.Queue()
    _sse_queues.setdefault(child_id, []).append(q)
    log.info("Dashboard SSE connected  child=%r", child_id)

    async def generator():
        history = db.get_events(child_id)
        yield f"data: {json.dumps({'type': 'history', 'events': history})}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    if event is _SSE_SHUTDOWN:
                        break
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # keep-alive heartbeat
                except asyncio.CancelledError:
                    break  # forced cancellation during shutdown
        finally:
            _sse_queues[child_id].remove(q)
            if not _sse_queues[child_id]:
                del _sse_queues[child_id]
            log.info("Dashboard SSE disconnected  child=%r", child_id)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/platforms")
def get_platforms() -> dict:
    """Return platform→process mappings, browser and transit process lists.

    Agents call this once on startup so that platform config is managed
    centrally on the server — no data files are needed on the child's machine.
    """
    return {
        "platforms": _platform_app_map,
        "browsers":  _browser_processes,
        "transit":   _transit_processes,
    }


@app.get("/health")
def health() -> dict:
    db_ok = db.ping()
    return {"status": "ok" if db_ok else "db_unavailable", "db": db_ok}


# ---------------------------------------------------------------------------
# Blocked words management
# ---------------------------------------------------------------------------


class WordRequest(BaseModel):
    word: str

    @field_validator("word", mode="after")
    @classmethod
    def _normalise(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("word must not be empty or whitespace")
        return v


@app.get("/api/words")
def get_words() -> dict:
    """Return the current in-memory blocked-words list."""
    words = _filter.words
    return {"count": len(words), "words": words}


@app.post("/api/words", status_code=201)
def create_word(body: WordRequest) -> dict:
    """Add a blocked word. Persists to MongoDB and reloads the in-memory set."""
    added = db.add_word(body.word)
    _load_blocked_words()
    log.info("Word %s  word=%r", "added" if added else "already existed", body.word)
    return {"ok": True, "word": body.word, "added": added}


@app.delete("/api/words/{word}")
def delete_word(word: str) -> dict:
    """Remove a blocked word. Persists to MongoDB and reloads the in-memory set."""
    word = word.strip().lower()
    if not word:
        raise HTTPException(status_code=400, detail="word must not be empty")
    removed = db.remove_word(word)
    _load_blocked_words()
    log.info("Word removed=%s  word=%r", removed, word)
    return {"ok": True, "word": word, "removed": removed}


@app.post("/api/words/reload")
def reload_words() -> dict:
    """Force an immediate reload of the blocked-words set from MongoDB."""
    _load_blocked_words()
    return {"ok": True, "count": len(_filter.words)}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@app.get("/api/events/{child_id}")
def get_events(child_id: str, limit: int = 100) -> dict:
    _validate_child_id(child_id)
    events = db.get_events(child_id)[: max(1, min(limit, 500))]
    return {"childId": child_id, "events": events, "count": len(events)}


@app.delete("/api/events/{child_id}")
def clear_events(child_id: str) -> dict:
    """Delete all stored hop events for a child (parent dashboard clear-history)."""
    _validate_child_id(child_id)
    deleted = db.clear_events(child_id)
    log.info("Events cleared  child=%r  count=%d", child_id, deleted)
    return {"ok": True, "childId": child_id, "deleted": deleted}


# ---------------------------------------------------------------------------
# Children
# ---------------------------------------------------------------------------


@app.get("/api/children")
def list_children() -> dict:
    """Return all registered children (plus any event-derived ones)."""
    return {"children": db.get_children()}


class RegisterChildRequest(BaseModel):
    child_id: Optional[str] = Field(None, alias="childId")
    child_name: str = Field("", alias="childName")

    model_config = {"populate_by_name": True}


@app.post("/api/children")
def register_child(body: RegisterChildRequest) -> dict:
    """Register a child on first connection (never overwrites an existing name).

    If *childId* is omitted the server generates a unique UUID and returns it.
    The agent should persist the returned childId locally so the same ID is
    reused across restarts.
    """
    child_id = (body.child_id or "").strip() or str(uuid.uuid4())
    name = body.child_name.strip() or child_id
    db.register_child(child_id, name)
    log.info("Child registered  id=%r  name=%r", child_id, name)
    return {"ok": True, "childId": child_id, "childName": name}


class RenameChildRequest(BaseModel):
    child_name: str = Field(..., alias="childName")
    model_config = {"populate_by_name": True}


@app.patch("/api/children/{child_id}")
def rename_child(child_id: str, body: RenameChildRequest) -> dict:
    """Rename an existing child (called from the Kids management page)."""
    _validate_child_id(child_id)
    name = body.child_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="childName must not be empty")
    db.rename_child(child_id, name)
    log.info("Child renamed  id=%r  name=%r", child_id, name)
    return {"ok": True, "childId": child_id, "childName": name}


# ---------------------------------------------------------------------------
# Demo seed  (dev / competition demo only — not for production)
# ---------------------------------------------------------------------------


@app.get("/api/demo/seed")
async def seed_demo() -> dict:
    """Inject a pre-baked demo session for childId='demo'.

    Only available when DEMO_MODE=true is set in the server environment.
    Disabled by default to prevent accidental data pollution in production.
    """
    if not _DEMO_MODE:
        raise HTTPException(status_code=404, detail="Not found.")
    base_time = time.time() - 1200  # events spread over the last 20 minutes

    demo_hops = [
        {
            "from": "explorer.exe",
            "to": "robloxplayerbeta.exe",
            "fromTitle": "Desktop",
            "toTitle": "Roblox",
        },
        {
            "from": "robloxplayerbeta.exe",
            "to": "chrome.exe",
            "fromTitle": "Roblox",
            "toTitle": "Google Chrome",
        },
        {
            "from": "chrome.exe",
            "to": "discord.exe",
            "fromTitle": "Chrome",
            "toTitle": "Discord",
            "detection": "confirmed_hop",
            "alertReason": "confirmed_hop",
            "classifyConfidence": 92,
            "classifyReason": "discord link shared in game chat",
            "classifySource": "server",
            "clickConfidence": "app_match",
        },
        {
            "from": "discord.exe",
            "to": "telegram.exe",
            "fromTitle": "Discord",
            "toTitle": "Telegram",
        },
        {
            "from": "telegram.exe",
            "to": "robloxplayerbeta.exe",
            "fromTitle": "Telegram",
            "toTitle": "Roblox",
        },
    ]

    inserted = []
    for i, hop in enumerate(demo_hops):
        event = {
            "childId": "demo",
            "source": "desktop",
            "from": hop["from"],
            "to": hop["to"],
            "fromTitle": hop["fromTitle"],
            "toTitle": hop["toTitle"],
            "timestamp": datetime.fromtimestamp(
                base_time + i * 240, tz=timezone.utc
            ).isoformat(),
            "blocked": False,
            "alert": hop.get("alertReason") is not None,
            "alertReason": hop.get("alertReason"),
            "receivedAt": datetime.now(timezone.utc).isoformat(),
            "detection": hop.get("detection"),
            "clickConfidence": hop.get("clickConfidence"),
            "classifyConfidence": hop.get("classifyConfidence"),
            "classifyReason": hop.get("classifyReason"),
            "classifySource": hop.get("classifySource"),
        }
        if event["alertReason"] is not None:
            db.insert_event(event)
        await _broadcast("demo", {"type": "event", **event})
        inserted.append(event)

    return {"seeded": len(inserted), "childId": "demo", "events": inserted}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info(
        "Starting HopMap server on %s:%d",
        config_manager.network.host,
        config_manager.network.port,
    )
    try:
        uvicorn.run(
            "server:app",
            host=config_manager.network.host,
            port=config_manager.network.port,
            reload=False,
            timeout_graceful_shutdown=2,
        )
    except KeyboardInterrupt:
        log.info("Server shutting down — goodbye.")
