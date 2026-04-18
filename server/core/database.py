import logging

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, PyMongoError

from config import config_manager

logger = logging.getLogger(__name__)


class DatabasePool:
    """Persistent MongoDB connection managed by PyMongo's MongoClient.

    Handles connection failures gracefully at startup — a warning is logged
    instead of crashing if MongoDB is temporarily unavailable.
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


_pool = DatabasePool(config_manager.db.mongo_uri, config_manager.db.db_name)
