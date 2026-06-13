import re

from pydantic import BaseModel, EmailStr, Field, field_validator


def _check_password_complexity(v: str) -> str:
    """Shared password complexity validator used by registration and password-reset schemas."""
    missing: list[str] = []
    if not re.search(r"[A-Z]", v):
        missing.append("one uppercase letter")
    if not re.search(r"[a-z]", v):
        missing.append("one lowercase letter")
    if not re.search(r"\d", v):
        missing.append("one digit")
    if not re.search(r"[^A-Za-z0-9]", v):
        missing.append("one special character")
    if missing:
        raise ValueError(f"Password must contain at least {', '.join(missing)}.")
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    # bcrypt silently truncates input at 72 bytes; 128 is a safe ceiling that
    # also blocks memory-exhaustion attempts on the hashing call.
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field("", alias="displayName", max_length=100)
    model_config = {"populate_by_name": True}

    @field_validator("display_name", mode="before")
    @classmethod
    def _strip_display_name(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    @field_validator("password")
    @classmethod
    def _validate_complexity(cls, v: str) -> str:
        return _check_password_complexity(v)


class UserResponse(BaseModel):
    id: str
    email: str
    displayName: str = ""
    createdAt: str = ""


class AuthResponse(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    user: UserResponse


class AccessTokenResponse(BaseModel):
    accessToken: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ValidateResetTokenRequest(BaseModel):
    token: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128, alias="newPassword")
    model_config = {"populate_by_name": True}

    @field_validator("new_password")
    @classmethod
    def _validate_complexity(cls, v: str) -> str:
        return _check_password_complexity(v)
