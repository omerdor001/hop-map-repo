from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from notifications import repository as notif_repo

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def get_notifications(unread: bool = False, current_user: dict = Depends(get_current_user)) -> dict:
    notifications = notif_repo.get_notifications(current_user["id"], unread_only=unread)
    return {"notifications": notifications, "count": len(notifications)}


@router.patch("/{notification_id}/read")
def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    updated = notif_repo.mark_notification_read(notification_id, current_user["id"])
    if not updated:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"ok": True}
