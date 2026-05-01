from pydantic import BaseModel


class OkResponse(BaseModel):
    """Generic acknowledgment response for mutation endpoints with no meaningful payload."""

    ok: bool = True
