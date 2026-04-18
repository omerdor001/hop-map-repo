from pydantic import BaseModel, field_validator


class WordRequest(BaseModel):
    word: str

    @field_validator("word", mode="after")
    @classmethod
    def _normalise(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("word must not be empty or whitespace")
        return v
