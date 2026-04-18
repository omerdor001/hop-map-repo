"""Pure unit tests for auth dependencies and utilities.

Covers password hashing, JWT lifecycle, refresh token generation,
and the two FastAPI dependency functions get_current_user / get_agent_child.
All database calls are mocked — no real MongoDB or running server needed.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt

_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from config import config_manager
from auth.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_token,
    verify_password,
)
from auth.dependencies import get_agent_child, get_current_user

_AUTH_CFG = config_manager.auth


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

class TestPasswordHashing:

    def test_hash_returns_string(self):
        assert isinstance(hash_password("secret123"), str)

    def test_hash_differs_from_plaintext(self):
        plain = "mypassword"
        assert hash_password(plain) != plain

    def test_two_calls_produce_different_hashes(self):
        assert hash_password("same") != hash_password("same")

    def test_verify_correct_password_returns_true(self):
        plain = "correct-horse-battery-staple"
        assert verify_password(plain, hash_password(plain)) is True

    def test_verify_wrong_password_returns_false(self):
        assert verify_password("wrong", hash_password("right")) is False

    def test_verify_empty_password_returns_false(self):
        assert verify_password("", hash_password("nonempty")) is False

    def test_verify_non_bcrypt_hash_returns_false(self):
        assert verify_password("anypassword", "not-a-bcrypt-hash") is False


# ---------------------------------------------------------------------------
# Access token (JWT)
# ---------------------------------------------------------------------------

class TestAccessToken:

    def test_create_returns_non_empty_string(self):
        token = create_access_token("uid-1", "a@b.com")
        assert isinstance(token, str) and len(token) > 0

    def test_decode_returns_correct_sub(self):
        token = create_access_token("uid-abc", "a@b.com")
        assert decode_access_token(token)["sub"] == "uid-abc"

    def test_decode_returns_correct_email(self):
        token = create_access_token("uid-abc", "a@b.com")
        assert decode_access_token(token)["email"] == "a@b.com"

    def test_decode_raises_401_for_garbage_string(self):
        with pytest.raises(HTTPException) as exc:
            decode_access_token("not.a.jwt")
        assert exc.value.status_code == 401

    def test_decode_raises_401_for_empty_string(self):
        with pytest.raises(HTTPException) as exc:
            decode_access_token("")
        assert exc.value.status_code == 401

    def test_decode_raises_401_for_tampered_signature(self):
        token = create_access_token("u1", "x@y.com")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(HTTPException) as exc:
            decode_access_token(tampered)
        assert exc.value.status_code == 401

    def test_decode_raises_401_for_expired_token(self):
        payload = {
            "sub": "u1", "email": "x@y.com",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        }
        expired = jwt.encode(payload, _AUTH_CFG.jwt_secret, algorithm=_AUTH_CFG.jwt_algorithm)
        with pytest.raises(HTTPException) as exc:
            decode_access_token(expired)
        assert exc.value.status_code == 401

    def test_decode_raises_401_for_wrong_secret(self):
        payload = {
            "sub": "u1", "email": "x@y.com",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        with pytest.raises(HTTPException) as exc:
            decode_access_token(token)
        assert exc.value.status_code == 401

    def test_tokens_for_different_users_differ(self):
        assert create_access_token("u1", "a@b.com") != create_access_token("u2", "a@b.com")


# ---------------------------------------------------------------------------
# Refresh token
# ---------------------------------------------------------------------------

class TestRefreshToken:

    def test_returns_two_non_empty_strings(self):
        raw, hashed = create_refresh_token()
        assert isinstance(raw, str) and len(raw) > 0
        assert isinstance(hashed, str) and len(hashed) > 0

    def test_raw_and_hash_differ(self):
        raw, hashed = create_refresh_token()
        assert raw != hashed

    def test_two_calls_return_different_raw_tokens(self):
        raw1, _ = create_refresh_token()
        raw2, _ = create_refresh_token()
        assert raw1 != raw2

    def test_returned_hash_matches_hash_token(self):
        raw, expected_hash = create_refresh_token()
        assert hash_token(raw) == expected_hash


# ---------------------------------------------------------------------------
# hash_token
# ---------------------------------------------------------------------------

class TestHashToken:

    def test_is_deterministic(self):
        assert hash_token("abc") == hash_token("abc")

    def test_different_inputs_produce_different_outputs(self):
        assert hash_token("aaa") != hash_token("bbb")

    def test_returns_lowercase_hex(self):
        result = hash_token("test-input")
        assert all(c in "0123456789abcdef" for c in result)

    def test_output_is_64_characters(self):
        assert len(hash_token("anything")) == 64

    def test_empty_string_produces_valid_hash(self):
        assert len(hash_token("")) == 64


# ---------------------------------------------------------------------------
# get_current_user dependency
# ---------------------------------------------------------------------------

class TestGetCurrentUser:

    async def test_valid_token_existing_user_returns_user(self):
        token = create_access_token("uid-1", "x@y.com")
        fake_user = {"id": "uid-1", "email": "x@y.com"}
        with patch("auth.dependencies.get_user_by_id", return_value=fake_user):
            result = await get_current_user(token=token)
        assert result == fake_user

    async def test_valid_token_user_not_found_raises_401(self):
        token = create_access_token("uid-gone", "gone@x.com")
        with patch("auth.dependencies.get_user_by_id", return_value=None):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(token=token)
        assert exc.value.status_code == 401

    async def test_invalid_token_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token="garbage.token.value")
        assert exc.value.status_code == 401

    async def test_token_without_sub_raises_401(self):
        payload = {
            "email": "x@y.com",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        token = jwt.encode(payload, _AUTH_CFG.jwt_secret, algorithm=_AUTH_CFG.jwt_algorithm)
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=token)
        assert exc.value.status_code == 401

    async def test_db_is_called_with_sub_from_token(self):
        token = create_access_token("uid-check", "test@test.com")
        with patch("auth.dependencies.get_user_by_id", return_value={"id": "uid-check"}) as mock_get:
            await get_current_user(token=token)
        mock_get.assert_called_once_with("uid-check")


# ---------------------------------------------------------------------------
# get_agent_child dependency
# ---------------------------------------------------------------------------

class TestGetAgentChild:

    def _make_request(self, auth_header: str | None) -> MagicMock:
        req = MagicMock()
        req.headers = {"Authorization": auth_header} if auth_header else {}
        return req

    async def test_valid_bearer_token_returns_child(self):
        raw, _ = create_refresh_token()
        fake_child = {"childId": "child-1", "parentId": "parent-1"}
        with patch("auth.dependencies.get_child_by_agent_token", return_value=fake_child):
            result = await get_agent_child(request=self._make_request(f"Bearer {raw}"))
        assert result == fake_child

    async def test_missing_authorization_header_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_agent_child(request=self._make_request(None))
        assert exc.value.status_code == 401

    async def test_non_bearer_scheme_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_agent_child(request=self._make_request("Basic dXNlcjpwYXNz"))
        assert exc.value.status_code == 401

    async def test_unknown_token_raises_401(self):
        with patch("auth.dependencies.get_child_by_agent_token", return_value=None):
            with pytest.raises(HTTPException) as exc:
                await get_agent_child(request=self._make_request("Bearer unknowntoken"))
        assert exc.value.status_code == 401

    async def test_raw_token_is_hashed_before_db_lookup(self):
        raw = "rawtoken-abc-123"
        expected_hash = hash_token(raw)
        with patch("auth.dependencies.get_child_by_agent_token", return_value=None) as mock_lookup:
            with pytest.raises(HTTPException):
                await get_agent_child(request=self._make_request(f"Bearer {raw}"))
        mock_lookup.assert_called_once_with(expected_hash)

    async def test_whitespace_stripped_from_bearer_token(self):
        raw = "cleantoken"
        expected_hash = hash_token(raw)
        with patch("auth.dependencies.get_child_by_agent_token", return_value=None) as mock_lookup:
            with pytest.raises(HTTPException):
                await get_agent_child(request=self._make_request(f"Bearer   {raw}   "))
        mock_lookup.assert_called_once_with(expected_hash)
