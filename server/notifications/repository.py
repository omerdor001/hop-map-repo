from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING

from core.database import _pool


def _col_notifications():
    return _pool.get_collection("notifications")


def insert_notification(parent_id: str, child_id: str, event_id: str, notif_type: str, message: str) -> str:
    result = _col_notifications().insert_one({
        "parentId": parent_id,
        "childId": child_id,
        "eventId": event_id,
        "type": notif_type,
        "message": message,
        "read": False,
        "createdAt": datetime.now(timezone.utc),
    })
    return str(result.inserted_id)


def get_notifications(parent_id: str, unread_only: bool = False) -> list[dict]:
    query: dict = {"parentId": parent_id}
    if unread_only:
        query["read"] = False
    cursor = _col_notifications().find(query).sort("createdAt", DESCENDING).limit(200)
    docs = []
    for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        doc["createdAt"] = doc["createdAt"].isoformat()
        docs.append(doc)
    return docs


def mark_notification_read(notification_id: str, parent_id: str) -> bool:
    try:
        result = _col_notifications().update_one(
            {"_id": ObjectId(notification_id), "parentId": parent_id},
            {"$set": {"read": True}},
        )
    except InvalidId:
        return False
    return result.modified_count > 0


def initialize_indexes() -> None:
    _col_notifications().create_index([("parentId", 1), ("read", 1), ("createdAt", DESCENDING)])
