from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from children.repository import get_children
from children.schemas import (
    ChildListResponse,
    ChildSummary,
    RegisterChildRequest,
    RegisterChildResponse,
    RenameChildRequest,
    RenameChildResponse,
)
from children import service as children_service
from core.schemas import OkResponse
from core.validators import validate_child_id

router = APIRouter(prefix="/api/children", tags=["children"])


@router.get("", response_model=ChildListResponse)
def list_children(current_user: dict = Depends(get_current_user)) -> ChildListResponse:
    return ChildListResponse(children=[ChildSummary(**c) for c in get_children(current_user["id"])])


@router.post("", status_code=201, response_model=RegisterChildResponse)
def register_child(body: RegisterChildRequest, current_user: dict = Depends(get_current_user)) -> RegisterChildResponse:
    result = children_service.add_child(
        body.child_id, body.child_name, current_user["id"],
        max_children=current_user.get("maxChildren", 1),
    )
    return RegisterChildResponse(**result)


@router.patch("/{child_id}", response_model=RenameChildResponse)
def rename_child(child_id: str, body: RenameChildRequest, current_user: dict = Depends(get_current_user)) -> RenameChildResponse:
    validate_child_id(child_id)
    result = children_service.update_child_name(child_id, body.child_name, current_user["id"])
    return RenameChildResponse(**result)


@router.delete("/{child_id}", response_model=OkResponse)
def delete_child(child_id: str, current_user: dict = Depends(get_current_user)) -> OkResponse:
    validate_child_id(child_id)
    children_service.remove_child(child_id, current_user["id"])
    return OkResponse()
