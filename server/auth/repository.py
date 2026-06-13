from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from core.database import pool
from plans import MAX_CHILDREN, Plan


def _col_users():
    return pool.get_collection("users")


def _col_sessions():
    return pool.get_collection("sessions")


def create_user(email: str, password_hash: str, display_name: str) -> str:
    result = _col_users().insert_one({
        "email":         email.lower().strip(),
        "passwordHash":  password_hash,
        "displayName":   display_name,
        "emailVerified": False,
        "plan":          Plan.FREE,
        "maxChildren":   MAX_CHILDREN[Plan.FREE],
        "createdAt":     datetime.now(timezone.utc),
        "deletedAt":     None,
    })
    return str(result.inserted_id)


def get_user_by_email(email: str) -> dict | None:
    doc = _col_users().find_one({"email": email.lower().strip(), "deletedAt": None})
    if doc:
        doc["id"] = str(doc.pop("_id"))
        if isinstance(doc.get("createdAt"), datetime):
            doc["createdAt"] = doc["createdAt"].isoformat()
    return doc


def get_user_by_id(user_id: str) -> dict | None:
    try:
        doc = _col_users().find_one({"_id": ObjectId(user_id), "deletedAt": None})
    except InvalidId:
        return None
    if doc:
        doc["id"] = str(doc.pop("_id"))
        if isinstance(doc.get("createdAt"), datetime):
            doc["createdAt"] = doc["createdAt"].isoformat()
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


def update_plan(user_id: str, plan: Plan) -> None:
    try:
        _col_users().update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"plan": plan, "maxChildren": MAX_CHILDREN[plan]}},
        )
    except InvalidId:
        pass


def update_telegram_chat_id(user_id: str, chat_id: str | None) -> None:
    try:
        _col_users().update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"telegramChatId": chat_id}},
        )
    except InvalidId:
        pass


def set_reset_token(user_id: str, token: str, expires_at: datetime) -> None:
    try:
        _col_users().update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"resetToken": token, "resetTokenExpiry": expires_at}},
        )
    except InvalidId:
        pass


def get_user_by_reset_token(token: str) -> dict | None:
    doc = _col_users().find_one({
        "resetToken": token,
        "resetTokenExpiry": {"$gt": datetime.now(timezone.utc)},
        "deletedAt": None,
    })
    if doc:
        doc["id"] = str(doc.pop("_id"))
        if isinstance(doc.get("createdAt"), datetime):
            doc["createdAt"] = doc["createdAt"].isoformat()
    return doc


def apply_password_reset(user_id: str, new_password_hash: str) -> None:
    """Set new password hash and clear the one-time reset token atomically."""
    try:
        _col_users().update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {"passwordHash": new_password_hash},
                "$unset": {"resetToken": "", "resetTokenExpiry": ""},
            },
        )
    except InvalidId:
        pass


def initialize_indexes() -> None:
    _col_users().create_index("email", unique=True)
    # sparse=True so the index only covers documents that actually have a reset token,
    # avoiding padding the index with nulls for the majority of users who don't.
    _col_users().create_index("resetToken", sparse=True)
    _col_sessions().create_index("tokenHash")
    _col_sessions().create_index("expiresAt", expireAfterSeconds=0)
