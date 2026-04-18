from datetime import datetime, timezone

from core.database import _pool


def _col_children():
    return _pool.get_collection("children")


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


def initialize_indexes() -> None:
    _col_children().create_index("childId", unique=True)
    _col_children().create_index("parentId")
    _col_children().create_index("agentTokenHash")
