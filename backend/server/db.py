import logging
from datetime import datetime, timezone

from pymongo import MongoClient, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, PyMongoError
from config import server_config

logger = logging.getLogger(__name__)


class DatabasePool:
    """Persistent MongoDB connection managed by PyMongo's MongoClient.

    Handles connection failures gracefully at startup — a warning is logged
    instead of crashing the server if MongoDB is temporarily unavailable.
    MongoClient maintains an internal connection pool and is thread-safe.
    """

    def __init__(self, uri: str, db_name: str):
        self.uri = uri
        self.db_name = db_name
        self._client: MongoClient | None = None
        self._db = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        try:
            self._client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=30000,
                maxPoolSize=50,
                minPoolSize=1,
            )
            self._client.admin.command("ping")
            self._db = self._client[self.db_name]
            logger.info("MongoDB connected: %s/%s", self.uri, self.db_name)
        except (ConnectionFailure, PyMongoError) as e:
            logger.warning("MongoDB unavailable at startup: %s", e)
            self._client = None
            self._db = None

    def get_collection(self, name: str) -> Collection:
        if self._db is None:
            raise RuntimeError("MongoDB is not connected")
        return self._db[name]

    def ping(self) -> bool:
        try:
            if self._client is None:
                return False
            self._client.admin.command("ping")
            return True
        except (ConnectionFailure, PyMongoError):
            return False

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None


_pool = DatabasePool(server_config.mongo_uri, server_config.db_name)


def _col_events() -> Collection:
    return _pool.get_collection(server_config.events_collection)


def _col_children() -> Collection:
    return _pool.get_collection("children")


def initialize_indexes() -> None:
    """Create MongoDB indexes. Call once from the server lifespan."""
    try:
        _col_events().create_index([("childId", 1), ("timestamp", DESCENDING)])
        _col_children().create_index("childId", unique=True)
        logger.info("MongoDB indexes ensured")
    except (RuntimeError, PyMongoError) as e:
        logger.warning("Could not create indexes: %s", e)


def ping() -> bool:
    """Returns True if the MongoDB connection is healthy."""
    return _pool.ping()


def insert_event(doc: dict) -> str:
    """Insert a hop event. Returns the inserted document's string id."""
    result = _col_events().insert_one(doc)
    return str(result.inserted_id)


def get_events(child_id: str) -> list[dict]:
    """Return all events for a child, newest first, with _id serialised to str."""
    cursor = _col_events().find({"childId": child_id}, {"_id": 0}).sort("timestamp", DESCENDING)
    return list(cursor)


def clear_events(child_id: str) -> int:
    """Delete all hop events for a child. Returns the number of deleted documents."""
    result = _col_events().delete_many({"childId": child_id})
    return result.deleted_count


def register_child(child_id: str, child_name: str) -> None:
    """Insert a child record only if it doesn't exist yet. Never overwrites the stored name."""
    _col_children().update_one(
        {"childId": child_id},
        {"$setOnInsert": {
            "childName": child_name,
            "registeredAt": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


def rename_child(child_id: str, child_name: str) -> bool:
    """Update the stored name for an existing child. Returns True if a doc was modified."""
    result = _col_children().update_one(
        {"childId": child_id},
        {"$set": {"childName": child_name}},
    )
    return result.modified_count > 0


def get_children() -> list[dict]:
    """Return all registered children, falling back to event-derived ones."""
    registered = {
        doc["childId"]: doc.get("childName", doc["childId"])
        for doc in _col_children().find({}, {"_id": 0, "childId": 1, "childName": 1})
    }
    # Also include any child that has events but was never explicitly registered.
    for cid in _col_events().distinct("childId"):
        registered.setdefault(cid, cid)
    return [{"childId": cid, "childName": name} for cid, name in sorted(registered.items())]

