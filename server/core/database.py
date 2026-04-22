import logging

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError

from config import config_manager
from core.db_circuit_breaker import DatabaseCircuitBreaker, _ProtectedCollection

logger = logging.getLogger(__name__)


class DatabasePool:
    """Persistent MongoDB connection managed by PyMongo's MongoClient.

    Every collection access goes through a _ProtectedCollection proxy that
    enforces the circuit breaker:  when MongoDB is unreachable, the circuit
    opens after `circuit_breaker_failure_threshold` consecutive failures and
    subsequent calls fast-fail with DatabaseCircuitOpenError (→ HTTP 503)
    until `circuit_breaker_recovery_timeout_seconds` elapses and a probe
    request succeeds.

    Handles connection failures gracefully at startup — a warning is logged
    instead of crashing if MongoDB is temporarily unavailable.
    """

    def __init__(self, uri: str, db_name: str) -> None:
        self.uri     = uri
        self.db_name = db_name
        self._client = None
        self._db     = None

        cfg = config_manager.db
        self.circuit_breaker = DatabaseCircuitBreaker(
            failure_threshold=cfg.circuit_breaker_failure_threshold,
            recovery_timeout=cfg.circuit_breaker_recovery_timeout_seconds,
        )

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
            self._db     = None

    def get_collection(self, name: str) -> _ProtectedCollection:
        """Return a circuit-breaker-protected proxy for the named collection.

        The proxy calls guard() before every operation, so DatabaseCircuitOpenError
        is raised at method-call time, not here.  This keeps the circuit check
        as close as possible to the actual network operation and avoids the
        false security of a stale CLOSED check done at collection-retrieval time.

        Raises:
            RuntimeError: If the initial connection to MongoDB was never
                established (client is None).
        """
        if self._db is None:
            raise RuntimeError("MongoDB is not connected")
        return _ProtectedCollection(self._db[name], self.circuit_breaker)

    def ping(self) -> bool:
        """Probe MongoDB connectivity directly, bypassing the circuit breaker.

        Intentionally bypasses the circuit so the health endpoint can always
        issue a real connectivity check and report accurate status.
        """
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
            self._db     = None


pool = DatabasePool(config_manager.db.mongo_uri, config_manager.db.db_name)
