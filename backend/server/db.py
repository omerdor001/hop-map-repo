import logging

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


def _col_settings() -> Collection:
    return _pool.get_collection(server_config.rules_collection)


def initialize_indexes() -> None:
    """Create MongoDB indexes. Call once from the server lifespan."""
    try:
        _col_events().create_index([("childId", 1), ("timestamp", DESCENDING)])
        _col_settings().create_index([("childId", 1)], unique=True)
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


# ── Settings (parent-controlled rules) ──────────────────────────────────────
# Single settings document per child stored in the 'rules' collection:
# {
#   "childId":   "child1",
#   "whitelist": ["robloxplayerbeta.exe"],  // silently skipped, never logged
#   "blacklist": ["discord.exe"],           // always logged as blocked
#   "rules":     [                          // per-app overrides
#     { "app": "steam.exe",    "action": "override_risk", "riskLevel": "LOW" },
#     { "app": "telegram.exe", "action": "alert" }
#   ]
# }

DEFAULT_SETTINGS = {
    "childName": "",   # display name set by parent
    "whitelist": [],   # apps silently skipped — never written to DB
    "blacklist": [],   # apps always logged as blocked
    "rules": [],       # per-app actions: alert
}


def get_settings(child_id: str) -> dict:
    """Return the settings doc for a child (defaults if none saved yet)."""
    doc = _col_settings().find_one({"childId": child_id}, {"_id": 0})
    if doc is None:
        return {"childId": child_id, **DEFAULT_SETTINGS}
    return doc


def upsert_settings(child_id: str, patch: dict) -> dict:
    """
    Replace whitelist, blacklist, and/or rules wholesale.
    Returns the full updated settings doc.
    """
    allowed = {k: v for k, v in patch.items() if k in ("childName", "whitelist", "blacklist", "rules")}
    _col_settings().update_one(
        {"childId": child_id},
        {"$set": {"childId": child_id, **allowed}},
        upsert=True,
    )
    return get_settings(child_id)


def _ensure_settings(child_id: str) -> None:
    """Guarantee a settings document exists for child_id."""
    _col_settings().update_one(
        {"childId": child_id},
        {"$setOnInsert": {"childId": child_id, **DEFAULT_SETTINGS}},
        upsert=True,
    )


def get_children() -> list[dict]:
    """Return a list of all known children with their id and display name."""
    docs = _col_settings().find({}, {"_id": 0, "childId": 1, "childName": 1})
    return list(docs)


def set_child_name(child_id: str, name: str) -> dict:
    """Set or update the display name for a child. Returns updated settings."""
    _ensure_settings(child_id)
    _col_settings().update_one({"childId": child_id}, {"$set": {"childName": name}})
    return get_settings(child_id)


def whitelist_add(child_id: str, app: str) -> dict:
    """Add *app* to the whitelist (stored lowercase, no duplicates)."""
    _ensure_settings(child_id)
    _col_settings().update_one({"childId": child_id}, {"$addToSet": {"whitelist": app.lower()}})
    return get_settings(child_id)


def whitelist_remove(child_id: str, app: str) -> dict:
    """Remove *app* from the whitelist."""
    _col_settings().update_one({"childId": child_id}, {"$pull": {"whitelist": app.lower()}})
    return get_settings(child_id)


def blacklist_add(child_id: str, app: str) -> dict:
    """Add *app* to the blacklist (stored lowercase, no duplicates)."""
    _ensure_settings(child_id)
    _col_settings().update_one({"childId": child_id}, {"$addToSet": {"blacklist": app.lower()}})
    return get_settings(child_id)


def blacklist_remove(child_id: str, app: str) -> dict:
    """Remove *app* from the blacklist."""
    _col_settings().update_one({"childId": child_id}, {"$pull": {"blacklist": app.lower()}})
    return get_settings(child_id)
