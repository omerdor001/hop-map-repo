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

from pydantic import ValidationError

from config import config_manager
from auth.schemas import RegisterRequest
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

    def test_corrupt_hash_returns_false(self):
        assert verify_password("anypassword", "not-a-bcrypt-hash") is False

    def test_unexpected_bcrypt_exception_propagates(self):
        with patch("auth.security.bcrypt.checkpw", side_effect=RuntimeError("internal bcrypt failure")):
            with pytest.raises(RuntimeError):
                verify_password("password", "any-hash")


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


# ---------------------------------------------------------------------------
# Password complexity validator (RegisterRequest)
# ---------------------------------------------------------------------------

def _make_register(password: str) -> RegisterRequest:
    """Convenience wrapper — constructs a RegisterRequest with a fixed valid email."""
    return RegisterRequest(email="user@example.com", password=password, display_name="")


def _complexity_errors(password: str) -> list[str]:
    """Return the list of error message strings raised by the complexity validator."""
    with pytest.raises(ValidationError) as exc:
        _make_register(password)
    return [e["msg"] for e in exc.value.errors() if e["loc"] == ("password",)]


@pytest.mark.unit
class TestPasswordComplexityValidator:
    """RegisterRequest must reject passwords that violate complexity rules.

    Each rule is tested in isolation (all other rules satisfied) so failures
    are unambiguous.  The golden path and boundary cases are also covered.
    """

    # ------------------------------------------------------------------
    # Golden path
    # ------------------------------------------------------------------

    def test_valid_password_is_accepted(self):
        req = _make_register("Correct#Horse9")
        assert req.password == "Correct#Horse9"

    def test_passphrase_with_all_rules_is_accepted(self):
        req = _make_register("Purple-Elephant-Dancing-2024!")
        assert req.password == "Purple-Elephant-Dancing-2024!"

    def test_minimum_length_with_all_rules_is_accepted(self):
        # Exactly 8 characters, all four character classes present.
        req = _make_register("Aa1!Aa1!")
        assert req.password == "Aa1!Aa1!"

    # ------------------------------------------------------------------
    # Each rule in isolation
    # ------------------------------------------------------------------

    def test_missing_uppercase_is_rejected(self):
        msgs = _complexity_errors("correct#horse9")
        assert len(msgs) == 1
        assert "uppercase" in msgs[0]

    def test_missing_lowercase_is_rejected(self):
        msgs = _complexity_errors("CORRECT#HORSE9")
        assert len(msgs) == 1
        assert "lowercase" in msgs[0]

    def test_missing_digit_is_rejected(self):
        msgs = _complexity_errors("Correct#Horse")
        assert len(msgs) == 1
        assert "digit" in msgs[0]

    def test_missing_special_character_is_rejected(self):
        msgs = _complexity_errors("CorrectHorse9")
        assert len(msgs) == 1
        assert "special" in msgs[0]

    # ------------------------------------------------------------------
    # Multiple failures reported in one error
    # ------------------------------------------------------------------

    def test_all_rules_missing_reported_in_single_error(self):
        # Lowercase only — missing uppercase, digit, special char.
        msgs = _complexity_errors("alllowercase")
        assert len(msgs) == 1
        assert "uppercase"  in msgs[0]
        assert "digit"      in msgs[0]
        assert "special"    in msgs[0]

    def test_two_rules_missing_listed_together(self):
        # No digit, no special character.
        msgs = _complexity_errors("CorrectHorse")
        assert len(msgs) == 1
        assert "digit"   in msgs[0]
        assert "special" in msgs[0]

    # ------------------------------------------------------------------
    # Pydantic field constraints (min/max length) still enforced
    # ------------------------------------------------------------------

    def test_password_below_min_length_is_rejected(self):
        with pytest.raises(ValidationError) as exc:
            _make_register("Ab1!")      # 4 chars — below min_length=8
        locs = [e["loc"] for e in exc.value.errors()]
        assert ("password",) in locs

    def test_password_at_bcrypt_truncation_boundary_is_accepted(self):
        # bcrypt truncates at 72 bytes.  A 72-char password with all rules
        # must be accepted — we validate the string, not its bcrypt input.
        pw = "Aa1!" + "x" * 68   # 72 chars total
        req = _make_register(pw)
        assert len(req.password) == 72

    # ------------------------------------------------------------------
    # Character-class boundary: common special characters
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("special", ["!", "@", "#", "$", "%", "-", "_", ".", " "])
    def test_various_special_characters_satisfy_rule(self, special):
        pw = f"CorrectHorse9{special}"
        req = _make_register(pw)
        assert req.password == pw
