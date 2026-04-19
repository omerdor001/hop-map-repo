from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AgentMeResponse(BaseModel):
    childId: str
    childName: str


class ActivateAgentRequest(BaseModel):
    setup_code: str = Field(..., alias="setupCode", min_length=1)
    model_config = {"populate_by_name": True}


class ActivateAgentResponse(BaseModel):
    agent_token: str = Field(..., alias="agentToken")

class ClassifyRequest(BaseModel):
    child_id: str = Field(..., alias="childId")
    url: str = Field(..., max_length=2048)
    context: str = Field(..., max_length=8192)
    source: str = "unknown"
    model_config = {"populate_by_name": True}


class ClassifyResponse(BaseModel):
    decision: str   # "YES" | "NO"
    confidence: int  # 0–100
    reason: str
    via: str = "server"


class HopEventRequest(BaseModel):
    from_app: str = Field("", alias="from")
    to_app: str = Field("", alias="to")
    from_title: str = Field("", alias="fromTitle")
    to_title: str = Field("", alias="toTitle")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    detection: str = ""
    click_confidence: str | None = Field(None, alias="clickConfidence")
    confirmed_to: str | None = Field(None, alias="confirmedTo")
    confirmed_to_title: str | None = Field(None, alias="confirmedToTitle")
    confirmed_at: str | None = Field(None, alias="confirmedAt")
    context: str | None = None
    classify_confidence: int | None = Field(None, alias="classifyConfidence")
    classify_reason: str | None = Field(None, alias="classifyReason")
    classify_source: str | None = Field(None, alias="classifySource")
    model_config = {"populate_by_name": True}
