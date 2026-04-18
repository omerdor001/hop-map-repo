from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from words import repository as words_repo
from words import service as words_service
from words.schemas import WordRequest

router = APIRouter(prefix="/api/words", tags=["words"])


@router.get("")
def get_words(_: dict = Depends(get_current_user)) -> dict:
    words = words_service.get_words()
    return {"count": len(words), "words": words}


@router.post("", status_code=201)
def create_word(body: WordRequest, _: dict = Depends(get_current_user)) -> dict:
    added = words_repo.add_word(body.word)
    words_service.load_blocked_words()
    return {"ok": True, "word": body.word, "added": added}


@router.delete("/{word}")
def delete_word(word: str, _: dict = Depends(get_current_user)) -> dict:
    word = word.strip().lower()
    if not word:
        raise HTTPException(status_code=400, detail="word must not be empty")
    removed = words_repo.remove_word(word)
    words_service.load_blocked_words()
    return {"ok": True, "word": word, "removed": removed}


@router.post("/reload")
def reload_words(_: dict = Depends(get_current_user)) -> dict:
    words_service.load_blocked_words()
    return {"ok": True, "count": len(words_service.get_words())}
