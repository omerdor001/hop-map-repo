from pydantic import BaseModel, Field, field_validator

_CHILD_NAME_MAX = 50


def _strip_str(v: object) -> object:
    return v.strip() if isinstance(v, str) else v


class RegisterChildRequest(BaseModel):
    child_id: str | None = Field(None, alias="childId")
    # Empty name is allowed — the service falls back to the child_id as display name.
    child_name: str = Field("", alias="childName", max_length=_CHILD_NAME_MAX)
    model_config = {"populate_by_name": True}

    @field_validator("child_name", mode="before")
    @classmethod
    def _strip_child_name(cls, v: object) -> object:
        return _strip_str(v)


class RenameChildRequest(BaseModel):
    child_name: str = Field(..., alias="childName", min_length=1, max_length=_CHILD_NAME_MAX)
    model_config = {"populate_by_name": True}

    @field_validator("child_name", mode="before")
    @classmethod
    def _strip_child_name(cls, v: object) -> object:
        return _strip_str(v)
