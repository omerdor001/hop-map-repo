from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from words import repository as words_repo
from words import service as words_service
from words.schemas import (
    CreateWordResponse,
    DeleteWordResponse,
    WordRequest,
    WordsListResponse,
    WordsReloadResponse,
)

router = APIRouter(prefix="/api/words", tags=["words"])


@router.get("", response_model=WordsListResponse)
def get_words(_: dict = Depends(get_current_user)) -> WordsListResponse:
    words = words_service.get_words()
    return WordsListResponse(count=len(words), words=words)


@router.post("", status_code=201, response_model=CreateWordResponse)
def create_word(body: WordRequest, _: dict = Depends(get_current_user)) -> CreateWordResponse:
    added = words_repo.add_word(body.word)
    words_service.load_blocked_words()
    return CreateWordResponse(ok=True, word=body.word, added=added)


@router.delete("/{word}", response_model=DeleteWordResponse)
def delete_word(word: str, _: dict = Depends(get_current_user)) -> DeleteWordResponse:
    word = word.strip().lower()
    if not word:
        raise HTTPException(status_code=400, detail="word must not be empty")
    removed = words_repo.remove_word(word)
    words_service.load_blocked_words()
    return DeleteWordResponse(ok=True, word=word, removed=removed)


@router.post("/reload", response_model=WordsReloadResponse)
def reload_words(_: dict = Depends(get_current_user)) -> WordsReloadResponse:
    words_service.load_blocked_words()
    return WordsReloadResponse(ok=True, count=len(words_service.get_words()))
