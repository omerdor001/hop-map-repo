from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from auth.repository import update_max_children, update_telegram_chat_id
from core.schemas import OkResponse

router = APIRouter(prefix="/api/me", tags=["profile"])


class UpdatePlanRequest(BaseModel):
    max_children: int = Field(..., alias="maxChildren", ge=0, le=100)
    model_config = {"populate_by_name": True}


class MeResponse(BaseModel):
    id: str
    email: str
    displayName: str = ""
    maxChildren: int = 0
    telegramChatId: str | None = None


class UpdatePlanResponse(BaseModel):
    ok: bool
    maxChildren: int


@router.get("", response_model=MeResponse)
def get_me(current_user: dict = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        id=current_user["id"],
        email=current_user["email"],
        displayName=current_user.get("displayName", ""),
        maxChildren=current_user.get("maxChildren", 0),
        telegramChatId=current_user.get("telegramChatId"),
    )


@router.patch("/plan", response_model=UpdatePlanResponse)
def update_plan(body: UpdatePlanRequest, current_user: dict = Depends(get_current_user)) -> UpdatePlanResponse:
    update_max_children(current_user["id"], body.max_children)
    return UpdatePlanResponse(ok=True, maxChildren=body.max_children)


@router.delete("/telegram", response_model=OkResponse)
def unlink_telegram(current_user: dict = Depends(get_current_user)) -> OkResponse:
    update_telegram_chat_id(current_user["id"], None)
    return OkResponse()
