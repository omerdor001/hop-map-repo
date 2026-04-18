import asyncio
import json
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from auth.dependencies import get_current_user
from config import config_manager
from core.validators import validate_child_id
from events import repository as event_repo
from events import service as event_service

log = logging.getLogger(__name__)

router = APIRouter(tags=["events"])

_HEARTBEAT_INTERVAL: float = 15.0


@router.get("/stream/{child_id}")
async def stream(child_id: str, request: Request) -> StreamingResponse:
    """SSE stream for parent dashboard. Access is scoped by child_id."""
    validate_child_id(child_id)

    q = event_service.register_listener(child_id)
    log.info("Dashboard SSE connected  child=%r", child_id)

    async def generator():
        try:
            history = event_repo.get_events(child_id)
        except Exception as exc:
            log.warning("SSE: failed to load history for child=%r: %s", child_id, exc)
            history = []
        yield f"data: {json.dumps({'type': 'history', 'events': history})}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=_HEARTBEAT_INTERVAL)
                    if event is event_service._SSE_SHUTDOWN:
                        break
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            event_service.unregister_listener(child_id, q)
            log.info("Dashboard SSE disconnected  child=%r", child_id)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/events/{child_id}")
def get_events(child_id: str, limit: int = 100, _: dict = Depends(get_current_user)) -> dict:
    validate_child_id(child_id)
    events = event_repo.get_events(child_id)[: max(1, min(limit, 500))]
    return {"childId": child_id, "events": events, "count": len(events)}


@router.delete("/api/events/{child_id}")
def clear_events(child_id: str, _: dict = Depends(get_current_user)) -> dict:
    validate_child_id(child_id)
    deleted = event_repo.clear_events(child_id)
    log.info("Events cleared  child=%r  count=%d", child_id, deleted)
    return {"ok": True, "childId": child_id, "deleted": deleted}


@router.get("/api/demo/seed")
async def seed_demo() -> dict:
    """Inject a pre-baked demo session. Only available when DEMO_MODE=true."""
    if not config_manager.demo_mode:
        raise HTTPException(status_code=404, detail="Not found.")
    base_time = time.time() - 1200

    demo_hops = [
        {"from": "explorer.exe", "to": "robloxplayerbeta.exe", "fromTitle": "Desktop", "toTitle": "Roblox"},
        {"from": "robloxplayerbeta.exe", "to": "chrome.exe", "fromTitle": "Roblox", "toTitle": "Google Chrome"},
        {
            "from": "chrome.exe", "to": "discord.exe", "fromTitle": "Chrome", "toTitle": "Discord",
            "detection": "confirmed_hop", "alertReason": "confirmed_hop",
            "classifyConfidence": 92, "classifyReason": "discord link shared in game chat",
            "classifySource": "server", "clickConfidence": "app_match",
        },
        {"from": "discord.exe", "to": "telegram.exe", "fromTitle": "Discord", "toTitle": "Telegram"},
        {"from": "telegram.exe", "to": "robloxplayerbeta.exe", "fromTitle": "Telegram", "toTitle": "Roblox"},
    ]

    inserted = []
    for i, hop in enumerate(demo_hops):
        event = {
            "childId": "demo", "source": "desktop",
            "from": hop["from"], "to": hop["to"],
            "fromTitle": hop["fromTitle"], "toTitle": hop["toTitle"],
            "timestamp": datetime.fromtimestamp(base_time + i * 240, tz=timezone.utc).isoformat(),
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
            event_repo.insert_event(event)
        await event_service.broadcast("demo", {"type": "event", **event})
        inserted.append(event)

    return {"seeded": len(inserted), "childId": "demo", "events": inserted}
