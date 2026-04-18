import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_agent_child
from children.repository import get_child_by_id
from classify import service as classify_service
from classify.schemas import ClassifyRequest, ClassifyResponse, HopEventRequest
from core.validators import validate_child_id
from events import repository as event_repo
from events import service as event_service
from notifications import repository as notif_repo
from words.service import check_blocked_words

log = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/classify", response_model=ClassifyResponse)
async def agent_classify(body: ClassifyRequest, _child: dict = Depends(get_agent_child)) -> ClassifyResponse:
    validate_child_id(body.child_id)
    if _child["childId"] != body.child_id:
        raise HTTPException(status_code=403, detail="Token does not match child.")
    if not await classify_service.check_rate_limit(body.child_id):
        log.warning("Classify rate limit hit  child=%r", body.child_id)
        raise HTTPException(status_code=429, detail="Classification rate limit exceeded.")

    log.info("Classifying  child=%r  source=%r  url=%s", body.child_id, body.source, body.url)

    word_found, matched_word = check_blocked_words(body.context)
    if word_found:
        log.info("Blocked word matched  child=%r  word=%r", body.child_id, matched_word)
        return ClassifyResponse(
            decision="YES", confidence=100,
            reason=f"blocked_word: {matched_word}", via="word_db",
        )

    try:
        result = await classify_service.run_classify(body.context)
    except json.JSONDecodeError as exc:
        log.warning("LLM returned non-JSON for child %r: %s", body.child_id, exc)
        return ClassifyResponse(decision="NO", confidence=0, reason="parse_error")
    except Exception as exc:
        log.warning("LLM error for child %r: %s", body.child_id, exc)
        return ClassifyResponse(decision="NO", confidence=0, reason="inference_error")

    log.info(
        "Classify result  child=%r  decision=%s  confidence=%d%%  reason=%r",
        body.child_id, result["decision"], result["confidence"], result["reason"],
    )
    result["via"] = "server"
    return ClassifyResponse(**result)


@router.post("/hop/{child_id}")
async def agent_hop(child_id: str, body: HopEventRequest, agent_child: dict = Depends(get_agent_child)) -> dict:
    validate_child_id(child_id)
    if agent_child["childId"] != child_id:
        raise HTTPException(status_code=403, detail="Token does not match child.")

    alert_reason: str | None = "confirmed_hop" if body.detection == "confirmed_hop" else None

    event = {
        "childId": child_id, "source": "desktop",
        "from": body.from_app, "to": body.to_app,
        "fromTitle": body.from_title, "toTitle": body.to_title,
        "timestamp": body.timestamp, "blocked": False,
        "alert": alert_reason is not None, "alertReason": alert_reason,
        "receivedAt": datetime.now(timezone.utc).isoformat(),
        "clickConfidence": body.click_confidence,
        "confirmedTo": body.confirmed_to, "confirmedToTitle": body.confirmed_to_title,
        "confirmedAt": body.confirmed_at, "context": body.context,
        "classifyConfidence": body.classify_confidence,
        "classifyReason": body.classify_reason, "classifySource": body.classify_source,
    }

    if alert_reason is not None and body.click_confidence != "switch_only":
        event_id = event_repo.insert_event(event)
        notif_repo.insert_notification(
            parent_id=agent_child["parentId"],
            child_id=child_id,
            event_id=event_id,
            notif_type="hop_detected",
            message=f"{agent_child.get('childName', child_id)} hopped to {body.confirmed_to or body.to_app}",
        )
    await event_service.broadcast(child_id, {"type": "event", **event})

    log.info(
        "Hop  %r → %r  (%r → %r)  alert=%s",
        event["from"], event["to"], event["fromTitle"], event["toTitle"],
        alert_reason or "none",
    )
    return {"ok": True}
