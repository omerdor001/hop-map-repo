import logging
import secrets
import uuid

from fastapi import HTTPException

from auth.security import hash_token
from children.repository import count_children, get_child_by_id, register_child, rename_child

log = logging.getLogger(__name__)


def add_child(child_id: str | None, child_name: str, parent_id: str, max_children: int) -> dict:
    if count_children(parent_id) >= max_children:
        raise HTTPException(status_code=403, detail="Child limit reached for your plan.")
    resolved_id = (child_id or "").strip() or str(uuid.uuid4())
    name = child_name.strip() or resolved_id
    raw_agent_token = secrets.token_hex(32)
    token_hash = hash_token(raw_agent_token)
    register_child(resolved_id, name, parent_id, token_hash, raw_agent_token[:8])
    log.info("Child registered  id=%r  name=%r  parent=%r", resolved_id, name, parent_id)
    return {"ok": True, "childId": resolved_id, "childName": name, "agentToken": raw_agent_token}


def update_child_name(child_id: str, child_name: str, parent_id: str) -> dict:
    updated = rename_child(child_id, parent_id, child_name)
    if not updated:
        raise HTTPException(status_code=404, detail="Child not found.")
    log.info("Child renamed  id=%r  name=%r  parent=%r", child_id, child_name, parent_id)
    return {"ok": True, "childId": child_id, "childName": child_name}
