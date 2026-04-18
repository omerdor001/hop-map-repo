import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from config import config_manager
from auth.repository import (
    create_session,
    create_user,
    get_session_by_hash,
    get_user_by_email,
    get_user_by_id,
    revoke_session,
)
from auth.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)

log = logging.getLogger(__name__)


def register(email: str, password: str, display_name: str) -> tuple[str, str, dict]:
    """Create a new parent account. Returns (access_token, raw_refresh_token, user_dict)."""
    normalized_email = email.lower().strip()
    try:
        user_id = create_user(normalized_email, hash_password(password), display_name or normalized_email)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Email already registered.")
    raw_token, token_hash = create_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=config_manager.auth.refresh_token_expire_days)
    create_session(user_id, token_hash, expires_at)
    log.info("User registered  id=%r  email=%r", user_id, normalized_email)
    return (
        create_access_token(user_id, normalized_email),
        raw_token,
        {"id": user_id, "email": normalized_email, "displayName": display_name or normalized_email},
    )


def login(email: str, password: str) -> tuple[str, str, dict]:
    """Validate credentials. Returns (access_token, raw_refresh_token, user_dict)."""
    user = get_user_by_email(email)
    if user is None or not verify_password(password, user["passwordHash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    raw_token, token_hash = create_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=config_manager.auth.refresh_token_expire_days)
    create_session(user["id"], token_hash, expires_at)
    log.info("User logged in  id=%r  email=%r", user["id"], user["email"])
    return (
        create_access_token(user["id"], user["email"]),
        raw_token,
        {"id": user["id"], "email": user["email"], "displayName": user.get("displayName", "")},
    )


def refresh(raw_token: str) -> tuple[str, str]:
    """Rotate refresh token. Returns (new_access_token, new_raw_refresh_token)."""
    token_hash = hash_token(raw_token)
    session = get_session_by_hash(token_hash)
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    user = get_user_by_id(session["userId"])
    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")
    revoke_session(token_hash)
    new_raw, new_hash = create_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=config_manager.auth.refresh_token_expire_days)
    create_session(user["id"], new_hash, expires_at)
    return create_access_token(user["id"], user["email"]), new_raw


def logout(raw_token: str | None) -> None:
    if raw_token:
        revoke_session(hash_token(raw_token))
