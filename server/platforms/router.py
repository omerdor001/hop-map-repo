from fastapi import APIRouter
from pydantic import BaseModel

from platforms import service as platforms_service

router = APIRouter(tags=["platforms"])


class PlatformsResponse(BaseModel):
    platforms: dict[str, list[str]]
    browsers: list[str]
    transit: list[str]


@router.get("/api/platforms", response_model=PlatformsResponse)
def get_platforms() -> PlatformsResponse:
    return PlatformsResponse(**platforms_service.get_platforms())
