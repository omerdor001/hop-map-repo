from datetime import datetime, timezone

from core.database import pool


def _col():
    return pool.get_collection("telegram_link_tokens")


def upsert_link_token(user_id: str, token_hash: str, expires_at: datetime) -> None:
    _col().update_one(
        {"userId": user_id},
        {"$set": {"tokenHash": token_hash, "expiresAt": expires_at}},
        upsert=True,
    )


def consume_link_token(token_hash: str) -> str | None:
    """Delete a matching unexpired token and return the associated user_id, or None."""
    doc = _col().find_one_and_delete({
        "tokenHash": token_hash,
        "expiresAt": {"$gt": datetime.now(timezone.utc)},
    })
    return doc["userId"] if doc else None


def initialize_indexes() -> None:
    _col().create_index("tokenHash")
    _col().create_index("expiresAt", expireAfterSeconds=0)
