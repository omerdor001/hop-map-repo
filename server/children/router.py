from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from children.repository import get_child_by_id, get_children
from children.schemas import RegisterChildRequest, RenameChildRequest
from children import service as children_service
from core.validators import validate_child_id

router = APIRouter(prefix="/api/children", tags=["children"])


@router.get("")
def list_children(current_user: dict = Depends(get_current_user)) -> dict:
    return {"children": get_children(current_user["id"])}


@router.post("", status_code=201)
def register_child(body: RegisterChildRequest, current_user: dict = Depends(get_current_user)) -> dict:
    return children_service.add_child(
        body.child_id, body.child_name, current_user["id"],
        max_children=current_user.get("maxChildren", 1),
    )


@router.patch("/{child_id}")
def rename_child(child_id: str, body: RenameChildRequest, current_user: dict = Depends(get_current_user)) -> dict:
    validate_child_id(child_id)
    if not get_child_by_id(child_id, current_user["id"]):
        raise HTTPException(status_code=403, detail="Child not found or not yours.")
    return children_service.update_child_name(child_id, body.child_name, current_user["id"])
