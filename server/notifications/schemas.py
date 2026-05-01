from typing import Any

from pydantic import BaseModel


class NotificationsResponse(BaseModel):
    notifications: list[dict[str, Any]]
    count: int
