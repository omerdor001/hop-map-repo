import re

from fastapi import HTTPException

_CHILD_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def validate_child_id(child_id: str) -> None:
    if not _CHILD_ID_RE.match(child_id):
        raise HTTPException(status_code=400, detail="Invalid childId format.")
