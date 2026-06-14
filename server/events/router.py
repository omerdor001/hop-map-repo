import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from auth.dependencies import get_current_user
from children.repository import get_child_by_id
from core.validators import validate_child_id
from events import repository as event_repo
from events.schemas import ClearEventsResponse, EventsResponse

log = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


@router.get("/api/events/{child_id}", response_model=EventsResponse)
def get_events(
    child_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
) -> EventsResponse:
    validate_child_id(child_id)
    if not get_child_by_id(child_id, current_user["id"]):
        raise HTTPException(status_code=403, detail="Child not found or not yours.")
    events = event_repo.get_events(child_id, limit=limit)
    return EventsResponse(childId=child_id, events=events, count=len(events))


@router.delete("/api/events/{child_id}", response_model=ClearEventsResponse)
def clear_events(
    child_id: str,
    current_user: dict = Depends(get_current_user),
) -> ClearEventsResponse:
    validate_child_id(child_id)
    if not get_child_by_id(child_id, current_user["id"]):
        raise HTTPException(status_code=403, detail="Child not found or not yours.")
    deleted = event_repo.clear_events(child_id)
    log.info("Events cleared  child=%r  count=%d", child_id, deleted)
    return ClearEventsResponse(ok=True, childId=child_id, deleted=deleted)
