from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from auth.repository import update_max_children

router = APIRouter(prefix="/api/me", tags=["me"])


class UpdatePlanRequest(BaseModel):
    max_children: int = Field(..., alias="maxChildren", ge=0, le=100)
    model_config = {"populate_by_name": True}


@router.get("")
def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "displayName": current_user.get("displayName", ""),
        "maxChildren": current_user.get("maxChildren", 0),
    }


@router.patch("/plan")
def update_plan(body: UpdatePlanRequest, current_user: dict = Depends(get_current_user)) -> dict:
    update_max_children(current_user["id"], body.max_children)
    return {"ok": True, "maxChildren": body.max_children}
