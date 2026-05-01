from pydantic import BaseModel, Field, field_validator


class WordRequest(BaseModel):
    word: str = Field(..., max_length=100)

    @field_validator("word", mode="after")
    @classmethod
    def _normalise(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("word must not be empty or whitespace")
        return v


class WordsListResponse(BaseModel):
    count: int
    words: list[str]


class CreateWordResponse(BaseModel):
    ok: bool
    word: str
    added: bool


class DeleteWordResponse(BaseModel):
    ok: bool
    word: str
    removed: bool


class WordsReloadResponse(BaseModel):
    ok: bool
    count: int
