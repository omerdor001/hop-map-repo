from pydantic import BaseModel


class EventsResponse(BaseModel):
    childId: str
    events: list[dict]
    count: int


class ClearEventsResponse(BaseModel):
    ok: bool
    childId: str
    deleted: int
