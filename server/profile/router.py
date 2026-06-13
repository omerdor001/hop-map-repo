from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth.dependencies import get_current_user
from auth.repository import update_telegram_chat_id
from core.schemas import OkResponse
from plans import MAX_CHILDREN, Plan

router = APIRouter(prefix="/api/me", tags=["profile"])


class MeResponse(BaseModel):
    id:             str
    email:          str
    displayName:    str        = ""
    plan:           Plan       = Plan.FREE
    maxChildren:    int        = MAX_CHILDREN[Plan.FREE]
    telegramChatId: str | None = None


def _parse_plan(value: object) -> Plan:
    try:
        return Plan(value)
    except (ValueError, TypeError):
        return Plan.FREE


@router.get("", response_model=MeResponse)
def get_me(current_user: dict = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        id=current_user["id"],
        email=current_user["email"],
        displayName=current_user.get("displayName", ""),
        plan=_parse_plan(current_user.get("plan")),
        maxChildren=current_user.get("maxChildren", MAX_CHILDREN[Plan.FREE]),
        telegramChatId=current_user.get("telegramChatId"),
    )


@router.delete("/telegram", response_model=OkResponse)
def unlink_telegram(current_user: dict = Depends(get_current_user)) -> OkResponse:
    update_telegram_chat_id(current_user["id"], None)
    return OkResponse()
