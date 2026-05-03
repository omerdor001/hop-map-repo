"""Unit tests for the words-DB service layer (words.service).

Tests load_blocked_words() and check_blocked_words() in isolation via
monkeypatch — no HTTP calls, no database, no server process.

The WordsFilter behaviour itself is covered exhaustively in test_words_filter.py.
This file focuses on:
  - load_blocked_words(): repository integration and atomic filter swap
  - Edge-case inputs: special chars (18+) and Hebrew Unicode
"""
import pytest

import words.service as words_svc
import words.repository as words_repo
from words.service import check_blocked_words, load_blocked_words
from words_filter import WordsFilter


def _seed(monkeypatch: pytest.MonkeyPatch, words: set[str]) -> None:
    """Inject a pre-built WordsFilter, bypassing the repository entirely."""
    f = WordsFilter()
    f.build(words)
    monkeypatch.setattr(words_svc, "_filter", f)


# ---------------------------------------------------------------------------
# load_blocked_words()
# ---------------------------------------------------------------------------

class TestLoadBlockedWords:
    """load_blocked_words() must rebuild _filter from words_repo."""

    def test_populates_filter_with_words_from_repo(self, monkeypatch):
        monkeypatch.setattr(words_repo, "get_blocked_words", lambda: {"hack", "18+"})
        load_blocked_words()
        found, matched = check_blocked_words("click here to hack your friends account")
        assert found is True
        assert matched == "hack"

    def test_empty_repo_clears_filter(self, monkeypatch):
        # Seed a non-empty filter first, then reload from an empty repo.
        _seed(monkeypatch, {"hack"})
        monkeypatch.setattr(words_repo, "get_blocked_words", lambda: set())
        load_blocked_words()
        found, _ = check_blocked_words("hack the planet")
        assert found is False

    def test_replaces_filter_reference_atomically(self, monkeypatch):
        """load_blocked_words() must swap _filter to a new instance, not mutate the old one."""
        original = words_svc._filter
        monkeypatch.setattr(words_repo, "get_blocked_words", lambda: {"hack"})
        load_blocked_words()
        assert words_svc._filter is not original

    def test_silently_logs_and_returns_on_repo_exception(self, monkeypatch):
        """A repository failure must not propagate — old filter stays in place."""
        _seed(monkeypatch, {"safe-word"})
        old_filter = words_svc._filter

        def _fail():
            raise RuntimeError("DB unavailable")

        monkeypatch.setattr(words_repo, "get_blocked_words", _fail)
        load_blocked_words()  # must not raise
        # Filter must remain unchanged after a failed reload.
        assert words_svc._filter is old_filter


# ---------------------------------------------------------------------------
# check_blocked_words() — special characters
# ---------------------------------------------------------------------------

class TestSpecialCharEntries:
    """Entries containing non-ASCII-word characters bypass the boundary check
    and are matched as substrings.  '18+' is the canonical example."""

    def test_detects_18plus(self, monkeypatch):
        _seed(monkeypatch, {"18+"})
        found, matched = check_blocked_words("check out this 18+ content")
        assert found is True
        assert matched == "18+"

    def test_18plus_not_triggered_by_unrelated_text(self, monkeypatch):
        _seed(monkeypatch, {"18+"})
        found, _ = check_blocked_words("come hang out with friends")
        assert found is False

    def test_reason_string_contains_matched_entry(self, monkeypatch):
        """Callers embed matched_word in the reason field; verify the value is exact."""
        _seed(monkeypatch, {"18+"})
        _, matched = check_blocked_words("this is 18+ material")
        assert matched == "18+"


# ---------------------------------------------------------------------------
# check_blocked_words() — Hebrew Unicode
# ---------------------------------------------------------------------------

class TestHebrewUnicodeEntries:
    """Hebrew entries must match as substrings (non-ASCII → no word-boundary check)."""

    def test_detects_hebrew_discord(self, monkeypatch):
        _seed(monkeypatch, {"דיסקורד"})
        found, matched = check_blocked_words("בוא לדיסקורד שלי זה מגניב")
        assert found is True
        assert matched == "דיסקורד"

    def test_hebrew_not_triggered_by_clean_english_text(self, monkeypatch):
        _seed(monkeypatch, {"דיסקורד"})
        found, _ = check_blocked_words("hey bro come check this cool server")
        assert found is False

    def test_mixed_filter_hebrew_and_english_each_match_independently(self, monkeypatch):
        _seed(monkeypatch, {"hack", "דיסקורד"})

        found_en, matched_en = check_blocked_words("click here to hack the game")
        assert found_en is True
        assert matched_en == "hack"

        found_he, matched_he = check_blocked_words("לך ל דיסקורד שלי")
        assert found_he is True
        assert matched_he == "דיסקורד"

    def test_empty_filter_does_not_match_hebrew(self, monkeypatch):
        _seed(monkeypatch, set())
        found, _ = check_blocked_words("בוא לדיסקורד שלי")
        assert found is False

