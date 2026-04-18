from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError

from core.database import _pool


def _col_users():
    return _pool.get_collection("users")


def _col_sessions():
    return _pool.get_collection("sessions")


def create_user(email: str, password_hash: str, display_name: str) -> str:
    result = _col_users().insert_one({
        "email": email.lower().strip(),
        "passwordHash": password_hash,
        "displayName": display_name,
        "emailVerified": False,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "deletedAt": None,
    })
    return str(result.inserted_id)


def get_user_by_email(email: str) -> dict | None:
    doc = _col_users().find_one({"email": email.lower().strip(), "deletedAt": None})
    if doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


def get_user_by_id(user_id: str) -> dict | None:
    try:
        doc = _col_users().find_one({"_id": ObjectId(user_id), "deletedAt": None})
    except InvalidId:
        return None
    if doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


def create_session(user_id: str, token_hash: str, expires_at: datetime) -> str:
    result = _col_sessions().insert_one({
        "userId": user_id,
        "tokenHash": token_hash,
        "createdAt": datetime.now(timezone.utc),
        "expiresAt": expires_at,
        "revokedAt": None,
    })
    return str(result.inserted_id)


def get_session_by_hash(token_hash: str) -> dict | None:
    return _col_sessions().find_one({
        "tokenHash": token_hash,
        "revokedAt": None,
        "expiresAt": {"$gt": datetime.now(timezone.utc)},
    })


def revoke_session(token_hash: str) -> None:
    _col_sessions().update_one(
        {"tokenHash": token_hash},
        {"$set": {"revokedAt": datetime.now(timezone.utc)}},
    )


def initialize_indexes() -> None:
    _col_users().create_index("email", unique=True)
    _col_sessions().create_index("tokenHash")
    _col_sessions().create_index("expiresAt", expireAfterSeconds=0)
