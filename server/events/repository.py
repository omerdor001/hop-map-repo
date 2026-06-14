from __future__ import annotations

from config import config_manager
from core.database import pool


def insert_event(doc: dict) -> str:
    col = pool.get_collection(config_manager.db.events_collection)
    result = col.insert_one(doc)
    return str(result.inserted_id)


def get_events(child_id: str, limit: int = 0) -> list[dict]:
    col = pool.get_collection(config_manager.db.events_collection)
    cursor = col.find({"childId": child_id}, {"_id": 0}).sort("timestamp", -1)
    if limit > 0:
        cursor = cursor.limit(limit)
    return list(cursor)


def clear_events(child_id: str) -> int:
    col = pool.get_collection(config_manager.db.events_collection)
    result = col.delete_many({"childId": child_id})
    return result.deleted_count


def initialize_indexes() -> None:
    col = pool.get_collection(config_manager.db.events_collection)
    col.create_index([("childId", 1), ("timestamp", -1)])
