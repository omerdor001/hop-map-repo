from pydantic import BaseModel, Field


class RegisterChildRequest(BaseModel):
    child_id: str | None = Field(None, alias="childId")
    child_name: str = Field("", alias="childName")
    model_config = {"populate_by_name": True}


class RenameChildRequest(BaseModel):
    child_name: str = Field(..., alias="childName")
    model_config = {"populate_by_name": True}
