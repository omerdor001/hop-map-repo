import io
import logging
import pathlib
import secrets
import zipfile
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from auth.dependencies import get_agent_child, get_current_user
from auth.security import hash_token
from agent_installer.generator import build_installer, build_uninstaller, build_readme, _AGENT_FILES, _SETUP_CODE_TTL_HOURS as _INSTALLER_TTL_HOURS
from children.repository import (
    get_child_by_id,
    get_child_by_setup_code_hash,
    consume_setup_code,
    upsert_setup_code,
)
from classify import service as classify_service
from classify.exceptions import (
    ClassifyError,
    LLMInferenceError,
    LLMResponseParseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from classify.schemas import (
    ActivateAgentRequest,
    ActivateAgentResponse,
    AgentMeResponse,
    ClassifyRequest,
    ClassifyResponse,
    HopEventRequest,
)
from core.validators import validate_child_id
from events import repository as event_repo
from events import service as event_service
from notifications import repository as notif_repo
from words.service import check_blocked_words

log = logging.getLogger(__name__)

# Root of the agent source directory, two levels up from this file (server/).
_AGENT_DIR = pathlib.Path(__file__).parent.parent.parent / "agent"

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/me", response_model=AgentMeResponse)
async def agent_me(agent_child: dict = Depends(get_agent_child)) -> AgentMeResponse:
    """Return the child identity associated with the bearer token."""
    return AgentMeResponse(
        childId=agent_child["childId"],
        childName=agent_child.get("childName", ""),
    )


@router.get("/files/{filename}")
def agent_file(filename: str) -> Response:
    """Serve a whitelisted agent source file for the installer to download.

    Only files explicitly listed in ``_AGENT_FILES`` are served — any other
    name returns 404, blocking path-traversal attempts entirely.
    """
    if filename not in _AGENT_FILES:
        raise HTTPException(status_code=404, detail="File not found.")

    file_path = _AGENT_DIR / filename
    if not file_path.exists():
        log.error("Agent file missing from disk: %s", file_path)
        raise HTTPException(status_code=404, detail="File not found.")

    content = file_path.read_bytes()
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/installer")
def agent_installer(
    child_id: str = Query(..., alias="childId", description="ID of the child to install the agent for"),
    backend_url: str = Query(..., alias="backendUrl", description="HopMap server base URL"),
    current_user: dict = Depends(get_current_user),
) -> Response:
    """Generate a per-child PowerShell installer with an embedded one-time setup code.

    The setup code is short-lived (1 h) and single-use — the agent exchanges it
    for its long-lived credential on first run via POST /agent/activate.  This
    means the .ps1 file itself contains no permanently sensitive material.

    Requires parent JWT; verifies the child belongs to the requesting parent.
    """
    child = get_child_by_id(child_id, current_user["id"])
    if child is None:
        raise HTTPException(status_code=404, detail="Child not found.")

    setup_code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=_INSTALLER_TTL_HOURS)
    upsert_setup_code(child_id, hash_token(setup_code), expires_at)

    child_name = child.get("childName", child_id)
    safe_filename = "".join(
        c for c in child_name if c.isalnum() or c in (" ", "_", "-")
    ).strip().replace(" ", "_") or "child"

    installer  = build_installer(backend_url=backend_url.rstrip("/"), setup_code=setup_code, child_name=child_name)
    uninstaller = build_uninstaller(child_name=child_name)
    readme      = build_readme(child_name=child_name, ttl_hours=_INSTALLER_TTL_HOURS)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt",             readme)
        zf.writestr("hopmap_install.ps1",    installer)
        zf.writestr("hopmap_uninstall.ps1",  uninstaller)
    buf.seek(0)

    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="hopmap_{safe_filename}.zip"',
        },
    )


@router.post("/activate", response_model=ActivateAgentResponse)
def agent_activate(body: ActivateAgentRequest) -> ActivateAgentResponse:
    """Exchange a one-time setup code for a long-lived agent token.

    Called by the agent on first run.  The setup code is burned immediately so
    re-use returns the same 400 as an expired or unknown code — no oracle leak.
    """
    code_hash = hash_token(body.setup_code)
    child = get_child_by_setup_code_hash(code_hash)

    if child is None:
        raise HTTPException(status_code=400, detail="Invalid or expired setup code.")

    expires_at_raw = child.get("setupCodeExpiresAt", "")
    try:
        expires_at = datetime.fromisoformat(expires_at_raw)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid or expired setup code.")

    if datetime.now(timezone.utc) >= expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired setup code.")

    new_token = secrets.token_hex(32)
    consume_setup_code(child["childId"], hash_token(new_token), new_token[:8])

    return ActivateAgentResponse(agentToken=new_token)


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
    except LLMResponseParseError as exc:
        log.warning(
            "LLM returned unparseable output  child=%r  raw=%r  cause=%s",
            body.child_id, exc.raw, exc.cause,
        )
        return ClassifyResponse(decision="NO", confidence=0, reason="llm_parse_error")
    except LLMUnavailableError as exc:
        log.error("Ollama unavailable  child=%r: %s", body.child_id, exc, exc_info=True)
        return ClassifyResponse(decision="NO", confidence=0, reason="llm_unavailable")
    except LLMTimeoutError as exc:
        log.warning("Ollama timed out  child=%r: %s", body.child_id, exc)
        return ClassifyResponse(decision="NO", confidence=0, reason="llm_timeout")
    except LLMInferenceError as exc:
        log.error("Ollama inference error  child=%r: %s", body.child_id, exc, exc_info=True)
        return ClassifyResponse(decision="NO", confidence=0, reason="llm_inference_error")
    except ClassifyError as exc:
        log.error(
            "Unexpected classify error  child=%r: %s", body.child_id, exc, exc_info=True,
        )
        return ClassifyResponse(decision="NO", confidence=0, reason="llm_error")

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
