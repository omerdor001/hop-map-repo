from datetime import datetime, timezone

from core.database import pool


def _col_children():
    return pool.get_collection("children")


def register_child(child_id: str, child_name: str, parent_id: str, agent_token_hash: str, agent_token_prefix: str) -> None:
    _col_children().update_one(
        {"childId": child_id},
        {"$setOnInsert": {
            "childName": child_name,
            "parentId": parent_id,
            "agentTokenHash": agent_token_hash,
            "agentTokenPrefix": agent_token_prefix,
            "registeredAt": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


def rename_child(child_id: str, child_name: str) -> bool:
    result = _col_children().update_one(
        {"childId": child_id},
        {"$set": {"childName": child_name}},
    )
    return result.modified_count > 0


def count_children(parent_id: str) -> int:
    return _col_children().count_documents({"parentId": parent_id})


def get_children(parent_id: str) -> list[dict]:
    return [
        {"childId": doc["childId"], "childName": doc.get("childName", doc["childId"])}
        for doc in _col_children().find(
            {"parentId": parent_id},
            {"_id": 0, "childId": 1, "childName": 1},
        )
    ]


def get_child_by_id(child_id: str, parent_id: str) -> dict | None:
    return _col_children().find_one({"childId": child_id, "parentId": parent_id}, {"_id": 0})


def get_child_by_agent_token(token_hash: str) -> dict | None:
    return _col_children().find_one({"agentTokenHash": token_hash}, {"_id": 0})


# ---------------------------------------------------------------------------
# Setup-code lifecycle (one-time activation tokens embedded in the installer)
# ---------------------------------------------------------------------------

def upsert_setup_code(child_id: str, code_hash: str, expires_at: datetime) -> None:
    """Store (or replace) a one-time setup code on an existing child document."""
    _col_children().update_one(
        {"childId": child_id},
        {"$set": {
            "setupCodeHash": code_hash,
            "setupCodeExpiresAt": expires_at.isoformat(),
        }},
    )


def get_child_by_setup_code_hash(code_hash: str) -> dict | None:
    """Return minimal child data for the given setup-code hash, or None."""
    return _col_children().find_one(
        {"setupCodeHash": code_hash},
        {"_id": 0, "childId": 1, "childName": 1, "setupCodeExpiresAt": 1},
    )


def consume_setup_code(child_id: str, new_token_hash: str, new_token_prefix: str) -> None:
    """Atomically burn the setup code and install the long-lived agent token.

    Using ``$set`` + ``$unset`` in a single update ensures the document is
    never in a state where both a valid setup code and a valid token coexist.
    """
    _col_children().update_one(
        {"childId": child_id},
        {
            "$set": {
                "agentTokenHash": new_token_hash,
                "agentTokenPrefix": new_token_prefix,
            },
            "$unset": {
                "setupCodeHash": "",
                "setupCodeExpiresAt": "",
            },
        },
    )


def initialize_indexes() -> None:
    _col_children().create_index("childId", unique=True)
    _col_children().create_index("parentId")
    _col_children().create_index("agentTokenHash")
    _col_children().create_index("setupCodeHash")
