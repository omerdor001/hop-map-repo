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
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import ollama
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import db
from config import server_config

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
    log.info("HopMap server starting.")
    db.initialize_indexes()
    yield
    log.info("HopMap server shutting down.")


app = FastAPI(title="HopMap API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=server_config.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Per-child SSE queues
# ---------------------------------------------------------------------------
# Each connected dashboard tab registers its own asyncio.Queue here.
# Structure: { child_id: [Queue, Queue, …] }

_sse_queues: dict[str, list[asyncio.Queue]] = {}


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
You are a child-safety monitor reviewing in-game chat messages.

Respond with a JSON object ONLY — no markdown fences, no explanation.
Schema:
{
  "decision":   "YES" or "NO",
  "confidence": integer 0-100,
  "reason":     "one short phrase (max 10 words)"
}

Reply YES if the message contains ANY of the following:
- A URL or link routing to an external / unmoderated platform
  (Discord, Telegram, WhatsApp, Snapchat, TikTok, Instagram, Signal, …)
- A username or handle on another platform
  ("add me on Discord: user#1234", "my snap is xyz")
- A direct request to move the conversation off the current platform
  ("DM me on insta", "join my Discord server", "hit me up on Telegram")
- A platform name paired with an invitation, even without a link

Reply NO if:
- The link points to a game wiki, patch notes, or official game resource
- The message is ordinary in-game chat with no external-platform reference
- The platform reference is incidental and carries no invitation
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
        window = _classify_call_times.setdefault(child_id, [])
        # Evict timestamps older than 60 s.
        _classify_call_times[child_id] = [t for t in window if now - t < 60.0]
        if len(_classify_call_times[child_id]) >= _CLASSIFY_MAX_RPM:
            return False
        _classify_call_times[child_id].append(now)
        return True


def _run_ollama_classify(context: str) -> dict:
    """Run Ollama synchronously and return a parsed result dict.

    Intended to be called via asyncio.to_thread so the event loop is never
    blocked during inference.

    Raises:
        json.JSONDecodeError: if the model response cannot be parsed as JSON.
        Exception:            for any Ollama / network failure.
    """
    response = ollama.chat(
        model=server_config.ollama_model,
        messages=[
            {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
            {"role": "user",   "content": context},
        ],
        options={"temperature": 0},
    )
    raw = response["message"]["content"].strip()
    # Strip markdown code fences that some model versions emit despite the
    # explicit instruction not to.
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    data = json.loads(raw)
    return {
        "decision":   str(data.get("decision", "NO")).upper(),
        "confidence": max(0, min(100, int(data.get("confidence", 50)))),
        "reason":     str(data.get("reason", "")).strip(),
    }


class ClassifyRequest(BaseModel):
    child_id: str = Field(..., alias="childId")
    url:      str
    context:  str
    source:   str = "unknown"   # "ocr" | "clipboard" | "unknown"

    model_config = {"populate_by_name": True}


class ClassifyResponse(BaseModel):
    decision:   str            # "YES" | "NO"
    confidence: int            # 0–100
    reason:     str
    via:        str = "server"


@app.post("/agent/classify", response_model=ClassifyResponse)
async def agent_classify(body: ClassifyRequest) -> ClassifyResponse:
    """Classify a URL + context snippet with the server-side LLM.

    Called by the desktop agent for every new URL it detects.  The agent sends
    only a few lines of chat context so the payload is small.  Inference is the
    dominant latency — typically 1–4 s on a modern CPU-only server with a 7B
    model, or sub-second on a GPU.

    Returns HTTP 429 if the per-child rate limit is exceeded.
    Returns decision="NO", confidence=0 on any inference error so the agent
    treats the result as a non-event rather than a false positive.
    """
    if not await _check_classify_rate_limit(body.child_id):
        log.warning(
            "Classify rate limit hit  child=%r — rejecting.", body.child_id
        )
        raise HTTPException(
            status_code=429,
            detail="Classification rate limit exceeded.",
        )

    log.info(
        "Classifying  child=%r  source=%r  url=%s",
        body.child_id, body.source, body.url,
    )

    try:
        result = await asyncio.to_thread(_run_ollama_classify, body.context)
    except json.JSONDecodeError as exc:
        log.warning(
            "Ollama returned non-JSON for child %r: %s", body.child_id, exc
        )
        return ClassifyResponse(decision="NO", confidence=0, reason="parse_error")
    except Exception as exc:
        log.warning("Ollama error for child %r: %s", body.child_id, exc)
        return ClassifyResponse(decision="NO", confidence=0, reason="inference_error")

    log.info(
        "Classify result  child=%r  decision=%s  confidence=%d%%  reason=%r",
        body.child_id, result["decision"], result["confidence"], result["reason"],
    )
    return ClassifyResponse(**result)


# ---------------------------------------------------------------------------
# Hop event ingestion
# ---------------------------------------------------------------------------

@app.post("/agent/hop/{child_id}")
async def agent_hop(child_id: str, request: Request) -> dict:
    """Desktop agent POSTs app-switch events here."""
    body = await request.json()

    settings = db.get_settings(child_id)
    to_app   = body.get("to", "").lower()

    # Whitelisted apps are silently dropped — no logging, no alert.
    whitelist = [w.lower() for w in settings.get("whitelist", [])]
    if to_app in whitelist:
        return {"ok": True, "skipped": True}

    # Blacklisted apps are always flagged as blocked.
    blacklist  = [b.lower() for b in settings.get("blacklist", [])]
    is_blocked = to_app in blacklist

    # Apply any per-app parent rule.
    rule   = next(
        (r for r in settings.get("rules", []) if r.get("app", "").lower() == to_app),
        None,
    )
    action = rule.get("action") if rule else None

    # Determine the alert reason (None → no alert).
    if is_blocked:
        alert_reason: Optional[str] = "blacklisted"
    elif action == "alert":
        alert_reason = "parent_rule"
    elif body.get("detection") == "confirmed_hop":
        alert_reason = "confirmed_hop"
    else:
        alert_reason = None

    event = {
        "childId":            child_id,
        "source":             "desktop",
        "from":               body.get("from", ""),
        "to":                 body.get("to", ""),
        "fromTitle":          body.get("fromTitle", ""),
        "toTitle":            body.get("toTitle", ""),
        "timestamp":          body.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "blocked":            is_blocked,
        "alert":              alert_reason is not None,
        "alertReason":        alert_reason,
        "receivedAt":         datetime.now(timezone.utc).isoformat(),
        # Click-confidence fields — present only on confirmed_hop events.
        "clickConfidence":    body.get("clickConfidence"),
        "confirmedTo":        body.get("confirmedTo"),
        "confirmedToTitle":   body.get("confirmedToTitle"),
        "confirmedAt":        body.get("confirmedAt"),
        "context":            body.get("context"),
        # Classification metadata forwarded from the agent.
        "classifyConfidence": body.get("classifyConfidence"),
        "classifyReason":     body.get("classifyReason"),
        "classifySource":     body.get("classifySource"),
    }

    # Only persist events that represent actual hop attempts.
    # Routine foreground switches with no alert reason are broadcast for live
    # display but are not written to the database.
    if alert_reason is not None:
        db.insert_event(event)

    await _broadcast(child_id, {"type": "event", **event})

    log.info(
        "Hop  %r → %r  (%r → %r)  alert=%s",
        event["from"], event["to"],
        event["fromTitle"], event["toTitle"],
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
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # keep-alive heartbeat
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

@app.get("/health")
def health() -> dict:
    db_ok = db.ping()
    return {"status": "ok" if db_ok else "db_unavailable", "db": db_ok}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@app.get("/api/events/{child_id}")
def get_events(child_id: str, limit: int = 100) -> dict:
    events = db.get_events(child_id)[: min(limit, 500)]
    return {"childId": child_id, "events": events, "count": len(events)}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.get("/api/settings/{child_id}")
def get_settings(child_id: str) -> dict:
    """Return the current rules for a child.

    The agent polls this endpoint periodically to pick up parent-dashboard
    changes without requiring a restart.
    """
    return db.get_settings(child_id)


@app.put("/api/settings/{child_id}")
async def update_settings(child_id: str, request: Request) -> dict:
    """Update rules or alert threshold for a child.

    Body (all fields optional)::

        {
            "alertThreshold": "MEDIUM",
            "whitelist": ["robloxplayerbeta.exe"],
            "blacklist": ["discord.exe"],
            "rules": [
                { "app": "steam.exe",    "action": "override_risk", "riskLevel": "LOW" },
                { "app": "telegram.exe", "action": "alert" }
            ]
        }
    """
    body    = await request.json()
    updated = db.upsert_settings(child_id, body)
    log.info("Settings updated  child=%r  %s", child_id, updated)
    return updated


# ---------------------------------------------------------------------------
# Children
# ---------------------------------------------------------------------------

@app.get("/api/children")
def list_children() -> dict:
    """Return all known children with their id and display name."""
    return {"children": db.get_children()}


@app.patch("/api/children/{child_id}/name")
async def set_child_name(child_id: str, request: Request) -> dict:
    """Set or update the display name for a child.  Body: ``{ "name": "Alice" }``"""
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="'name' must not be empty.")
    updated = db.set_child_name(child_id, name)
    log.info("Child name set  child=%r  name=%r", child_id, name)
    return {"childId": child_id, "childName": updated.get("childName", "")}


# ---------------------------------------------------------------------------
# Whitelist
# ---------------------------------------------------------------------------

@app.get("/api/settings/{child_id}/whitelist")
def get_whitelist(child_id: str) -> dict:
    return {
        "childId":   child_id,
        "whitelist": db.get_settings(child_id).get("whitelist", []),
    }


@app.post("/api/settings/{child_id}/whitelist", status_code=201)
async def add_to_whitelist(child_id: str, request: Request) -> dict:
    """Add an app to the whitelist.  Body: ``{ "app": "robloxplayerbeta.exe" }``"""
    body = await request.json()
    return db.whitelist_add(child_id, body["app"])


@app.delete("/api/settings/{child_id}/whitelist/{app}")
def remove_from_whitelist(child_id: str, app: str) -> dict:
    return db.whitelist_remove(child_id, app)


# ---------------------------------------------------------------------------
# Blacklist
# ---------------------------------------------------------------------------

@app.get("/api/settings/{child_id}/blacklist")
def get_blacklist(child_id: str) -> dict:
    return {
        "childId":   child_id,
        "blacklist": db.get_settings(child_id).get("blacklist", []),
    }


@app.post("/api/settings/{child_id}/blacklist", status_code=201)
async def add_to_blacklist(child_id: str, request: Request) -> dict:
    """Add an app to the blacklist.  Body: ``{ "app": "discord.exe" }``"""
    body = await request.json()
    return db.blacklist_add(child_id, body["app"])


@app.delete("/api/settings/{child_id}/blacklist/{app}")
def remove_from_blacklist(child_id: str, app: str) -> dict:
    return db.blacklist_remove(child_id, app)


# ---------------------------------------------------------------------------
# Demo seed  (dev / competition demo only — not for production)
# ---------------------------------------------------------------------------

@app.get("/api/demo/seed")
async def seed_demo() -> dict:
    """Inject a pre-baked demo session for childId='demo'.

    Useful for live demonstrations and UI development.
    """
    base_time = time.time() - 1200  # events spread over the last 20 minutes

    demo_hops = [
        {
            "from": "explorer.exe",         "to": "robloxplayerbeta.exe",
            "fromTitle": "Desktop",         "toTitle": "Roblox",
        },
        {
            "from": "robloxplayerbeta.exe", "to": "chrome.exe",
            "fromTitle": "Roblox",          "toTitle": "Google Chrome",
        },
        {
            "from": "chrome.exe",           "to": "discord.exe",
            "fromTitle": "Chrome",          "toTitle": "Discord",
            "detection": "confirmed_hop",   "alertReason": "confirmed_hop",
            "classifyConfidence": 92,
            "classifyReason":     "discord link shared in game chat",
            "classifySource":     "server",
            "clickConfidence":    "app_match",
        },
        {
            "from": "discord.exe",          "to": "telegram.exe",
            "fromTitle": "Discord",         "toTitle": "Telegram",
        },
        {
            "from": "telegram.exe",         "to": "robloxplayerbeta.exe",
            "fromTitle": "Telegram",        "toTitle": "Roblox",
        },
    ]

    inserted = []
    for i, hop in enumerate(demo_hops):
        event = {
            "childId":            "demo",
            "source":             "desktop",
            "from":               hop["from"],
            "to":                 hop["to"],
            "fromTitle":          hop["fromTitle"],
            "toTitle":            hop["toTitle"],
            "timestamp":          base_time + i * 240,
            "blocked":            False,
            "alert":              hop.get("alertReason") is not None,
            "alertReason":        hop.get("alertReason"),
            "receivedAt":         datetime.now(timezone.utc).isoformat(),
            "detection":          hop.get("detection"),
            "clickConfidence":    hop.get("clickConfidence"),
            "classifyConfidence": hop.get("classifyConfidence"),
            "classifyReason":     hop.get("classifyReason"),
            "classifySource":     hop.get("classifySource"),
        }
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
        server_config.host, server_config.port,
    )
    try:
        uvicorn.run(
            "server:app",
            host=server_config.host,
            port=server_config.port,
            reload=False,
        )
    except KeyboardInterrupt:
        log.info("Server shutting down — goodbye.")