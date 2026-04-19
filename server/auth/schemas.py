from pydantic import BaseModel, EmailStr, Field, field_validator


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
