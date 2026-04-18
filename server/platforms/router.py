from fastapi import APIRouter

from platforms import service as platforms_service

router = APIRouter(tags=["platforms"])


@router.get("/api/platforms")
def get_platforms() -> dict:
    return platforms_service.get_platforms()
