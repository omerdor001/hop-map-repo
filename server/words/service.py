import asyncio
import logging
import os

from config import config_manager
from words_filter import WordsFilter
from words import repository as words_repo

log = logging.getLogger(__name__)

_filter: WordsFilter = WordsFilter()
_words_refresh_task: asyncio.Task | None = None


def load_blocked_words() -> None:
    global _filter
    try:
        entries = words_repo.get_blocked_words()
        new_filter = WordsFilter()
        new_filter.build(entries)
        _filter = new_filter  # atomic reference swap — callers always see a fully-built filter
        log.info(
            "Blocked entries reloaded: %d total (%d single-word, %d phrase)",
            new_filter.entry_count, len(new_filter.words), new_filter.entry_count - len(new_filter.words),
        )
    except Exception as exc:
        log.warning("Failed to reload blocked words from MongoDB: %s", exc)


def check_blocked_words(text: str) -> tuple[bool, str]:
    found, matched = _filter.find(text)
    if found:
        log.info("Blocked entry detected: '%s'", matched)
    return found, matched


def get_words() -> list[str]:
    return _filter.words


def get_entry_count() -> int:
    return _filter.entry_count


def is_refresh_task_alive() -> bool:
    return _words_refresh_task is not None and not _words_refresh_task.done()


async def _refresh_loop() -> None:
    interval = config_manager.db.words_refresh_interval_seconds
    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return
        await asyncio.to_thread(load_blocked_words)


async def start_refresh_task() -> None:
    global _words_refresh_task
    _words_refresh_task = asyncio.create_task(_refresh_loop())


async def stop_refresh_task() -> None:
    if _words_refresh_task is not None:
        _words_refresh_task.cancel()
        await asyncio.gather(_words_refresh_task, return_exceptions=True)


def seed_if_empty(words_path: str) -> None:
    if not words_repo.has_words() and words_path and os.path.exists(words_path):
        seeded = words_repo.seed_words_from_excel(words_path)
        log.info("Seeded %d words from Excel into MongoDB words collection", seeded)
