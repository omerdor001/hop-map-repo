import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from config import config_manager
from auth.email_service import send_password_reset_email
from auth.repository import (
    apply_password_reset,
    create_session,
    create_user,
    get_session_by_hash,
    get_user_by_email,
    get_user_by_id,
    get_user_by_reset_token,
    revoke_session,
    set_reset_token,
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


def forgot_password(email: str) -> None:
    """Generate a reset token and send an email. Always returns silently to prevent enumeration."""
    user = get_user_by_email(email)
    if user is None:
        return

    cfg = config_manager.email
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=cfg.reset_token_expiry_minutes)
    set_reset_token(user["id"], token, expires_at)

    base_url = cfg.reset_password_url.rstrip("/")
    reset_link = f"{base_url}/reset-password?token={token}"
    send_password_reset_email(email, reset_link)
    log.info("Password reset requested for user id=%r email=%r", user["id"], email)


def validate_reset_token(token: str) -> None:
    """Raise 401 if token is invalid or expired."""
    if get_user_by_reset_token(token) is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired reset link. Please request a new password reset.",
        )


def reset_password(token: str, new_password: str) -> None:
    """Apply new password and invalidate the token. Raises 401 if token is invalid/expired."""
    user = get_user_by_reset_token(token)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired reset link. Please request a new password reset.",
        )
    apply_password_reset(user["id"], hash_password(new_password))
    log.info("Password reset successful for user id=%r email=%r", user["id"], user["email"])
