"""FastAPI dependency functions for authentication.

Thin layer that wires security utilities and repositories into FastAPI's
dependency injection system. No business logic lives here.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from auth.repository import get_user_by_id
from auth.security import decode_access_token, hash_token, oauth2_scheme
from children.repository import get_child_by_agent_token


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_access_token(token)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user


async def get_agent_child(request: Request) -> dict:
    """Validate agent Bearer token and return the child document."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing agent token.")
    raw_token = auth_header.removeprefix("Bearer ").strip()
    child = get_child_by_agent_token(hash_token(raw_token))
    if child is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent token.")
    return child
