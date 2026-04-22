from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from config import config_manager


class AgentMeResponse(BaseModel):
    childId: str
    childName: str


class ActivateAgentRequest(BaseModel):
    # Real setup codes are token_urlsafe(32) — 43 URL-safe base64 chars.
    # Pattern rejects non-URL-safe chars early without leaking whether a
    # valid-format code exists (same 400 path handles unknown/expired codes).
    setup_code: str = Field(
        ...,
        alias="setupCode",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    model_config = {"populate_by_name": True}


class ActivateAgentResponse(BaseModel):
    agent_token: str = Field(..., alias="agentToken")


class ClassifyRequest(BaseModel):
    child_id: str = Field(..., alias="childId")
    url: str = Field(..., max_length=2048)
    context: str = Field(..., min_length=1, max_length=config_manager.classify_context_max_chars)
    source: str = Field("unknown", max_length=64)
    model_config = {"populate_by_name": True}


class ClassifyResponse(BaseModel):
    decision: Literal["YES", "NO"]
    confidence: int = Field(..., ge=0, le=100)
    reason: str = Field(..., max_length=200)
    via: str = Field("server", max_length=32)


class HopEventRequest(BaseModel):
    from_app: str = Field("", alias="from", max_length=256)
    to_app: str = Field("", alias="to", max_length=256)
    from_title: str = Field("", alias="fromTitle", max_length=512)
    to_title: str = Field("", alias="toTitle", max_length=512)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        max_length=64,
    )
    detection: str = Field("", max_length=64)
    click_confidence: str | None = Field(None, alias="clickConfidence", max_length=64)
    confirmed_to: str | None = Field(None, alias="confirmedTo", max_length=256)
    confirmed_to_title: str | None = Field(None, alias="confirmedToTitle", max_length=512)
    confirmed_at: str | None = Field(None, alias="confirmedAt", max_length=64)
    context: str | None = Field(None, max_length=8192)
    classify_confidence: int | None = Field(None, alias="classifyConfidence", ge=0, le=100)
    classify_reason: str | None = Field(None, alias="classifyReason", max_length=200)
    classify_source: str | None = Field(None, alias="classifySource", max_length=64)
    model_config = {"populate_by_name": True}
