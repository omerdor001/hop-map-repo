from typing import Any

from pydantic import BaseModel


class EventsResponse(BaseModel):
    childId: str
    events: list[dict[str, Any]]
    count: int


class ClearEventsResponse(BaseModel):
    ok: bool
    childId: str
    deleted: int


class DemoSeedResponse(BaseModel):
    seeded: int
    childId: str
    events: list[dict[str, Any]]
