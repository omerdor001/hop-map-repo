"""
Multi-pattern blocked-words filter using Aho-Corasick.

Replaces the previous two-path approach (phrase substring search + regex
tokenisation) with a single automaton scan that is correct for all character
sets, including special-char entries like '18+' and Unicode scripts like Hebrew.

Algorithm
─────────
  Aho-Corasick scans the text once in O(n + matches) time, reporting every
  position where a stored pattern ends.  For pure ASCII word-char entries
  (e.g. "hack") a word-boundary check is applied so "hackle" does not trigger
  "hack".  Entries that contain non-ASCII characters or characters outside
  [a-zA-Z0-9_] skip the boundary check and are matched as substrings (the
  same behaviour as the previous phrase path).

  When multiple patterns match, the *longest* match is returned; ties are
  broken by earliest start position in the text.  This preserves the original
  intent of "most-specific match wins" that the previous phrase-first priority
  implemented.
"""

from __future__ import annotations

import re
from typing import Iterable

import ahocorasick

# Compiled once — matches entries that only contain ASCII word characters.
# These entries require a word-boundary check to avoid false positives like
# "hackle" matching "hack".
_ASCII_WORD_RE = re.compile(r"^[a-zA-Z0-9_]+$")


def _needs_boundary_check(entry: str) -> bool:
    """Return True if *entry* requires word-boundary validation on match."""
    return bool(_ASCII_WORD_RE.match(entry))


def _is_word_boundary(text: str, start: int, end: int) -> bool:
    """Return True if the match at [start, end) is surrounded by non-word chars.

    A position before index 0 or after the last index counts as a boundary.
    Only called for ASCII-word entries; not safe to use on arbitrary Unicode
    because Python's \\b semantics differ from the automaton's byte positions.
    """
    before_ok = start == 0 or not text[start - 1].isalnum() and text[start - 1] != "_"
    after_ok  = end == len(text) or not text[end].isalnum() and text[end] != "_"
    return before_ok and after_ok


class WordsFilter:
    """Aho-Corasick based multi-pattern filter for blocked words and phrases.

    Usage::

        f = WordsFilter()
        f.build(["hack", "18+", "don't tell your parents"])
        found, matched = f.find("check out this 18+ content")
        # found=True, matched='18+'
    """

    def __init__(self) -> None:
        self._automaton: ahocorasick.Automaton | None = None
        self._entry_needs_boundary: dict[str, bool] = {}
        self._all_entries: list[str] = []
        self._words_cache: list[str] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def build(self, entries: Iterable[str]) -> None:
        """(Re-)build the automaton from *entries*.

        All entries are lowercased before storage so that :meth:`find` only
        needs to lowercase the input text once.  Duplicate entries (after
        lowercasing) are silently deduplicated.

        If the entry list is empty the automaton is cleared; subsequent calls
        to :meth:`find` will return ``(False, "")``.
        """
        normalised = sorted({e.lower() for e in entries if e.strip()})
        self._all_entries = normalised
        self._words_cache = [e for e in normalised if " " not in e]
        self._entry_needs_boundary = {e: _needs_boundary_check(e) for e in normalised}

        if not normalised:
            self._automaton = None
            return

        automaton = ahocorasick.Automaton()
        for entry in normalised:
            automaton.add_word(entry, entry)
        automaton.make_automaton()
        self._automaton = automaton

    def find(self, text: str) -> tuple[bool, str]:
        """Scan *text* for any blocked entry.

        Returns ``(True, matched_entry)`` for the longest match found
        (earliest start position as tiebreak), or ``(False, "")`` if no
        blocked entry is present.
        """
        if self._automaton is None or not text:
            return False, ""

        text_lower = text.lower()
        best_entry = ""
        best_length = 0

        for end_idx, entry in self._automaton.iter(text_lower):
            start_idx = end_idx - len(entry) + 1

            if self._entry_needs_boundary[entry]:
                if not _is_word_boundary(text_lower, start_idx, end_idx + 1):
                    continue

            # Prefer longer matches; for equal length prefer leftmost position.
            if len(entry) > best_length or (
                len(entry) == best_length and start_idx < (end_idx - len(best_entry) + 1)
            ):
                best_entry = entry
                best_length = len(entry)

        if best_entry:
            return True, best_entry
        return False, ""

    # ------------------------------------------------------------------
    # Properties for server.py consumers
    # ------------------------------------------------------------------

    @property
    def words(self) -> list[str]:
        """Sorted list of single-token (no-space) entries.

        Mirrors the previous ``sorted(_blocked_words)`` used by the
        ``GET /api/words`` endpoint — multi-word phrases are excluded so the
        API response shape is unchanged.
        """
        return self._words_cache

    @property
    def entry_count(self) -> int:
        """Total number of entries (words + phrases) stored in the filter."""
        return len(self._all_entries)
