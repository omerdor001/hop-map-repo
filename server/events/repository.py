from pymongo import DESCENDING

from core.database import pool
from config import config_manager


def _col_events():
    return pool.get_collection(config_manager.db.events_collection)


def insert_event(doc: dict) -> str:
    result = _col_events().insert_one({**doc})
    return str(result.inserted_id)


def get_events(child_id: str) -> list[dict]:
    cursor = _col_events().find({"childId": child_id}, {"_id": 0}).sort("timestamp", DESCENDING)
    return list(cursor)


def clear_events(child_id: str) -> int:
    result = _col_events().delete_many({"childId": child_id})
    return result.deleted_count


def initialize_indexes() -> None:
    _col_events().create_index([("childId", 1), ("timestamp", DESCENDING)])
