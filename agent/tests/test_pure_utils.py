"""Unit tests for pure helper functions in agent.py.

These functions have no side-effects and require no mocking beyond the
module-level stubs already injected by conftest.py.
"""
from __future__ import annotations

import importlib
import sys

import pytest


# ---------------------------------------------------------------------------
# Import agent module (conftest.py has already stubbed Windows deps)
# ---------------------------------------------------------------------------

import agent as _agent


class TestFindUrls:

    def test_empty_string_returns_empty_list(self):
        assert _agent._find_urls("") == []

    def test_single_https_url_extracted(self):
        urls = _agent._find_urls("Check out https://discord.gg/abc123")
        assert "https://discord.gg/abc123" in urls

    def test_http_url_extracted(self):
        urls = _agent._find_urls("visit http://example.com/page")
        assert "http://example.com/page" in urls

    def test_multiple_urls_extracted(self):
        text = "go to https://discord.gg/abc and https://t.me/xyz"
        urls = _agent._find_urls(text)
        assert len(urls) == 2

    def test_trailing_punctuation_stripped(self):
        urls = _agent._find_urls("link: https://discord.gg/abc.")
        assert urls[0].endswith("abc")  # dot stripped

    def test_bare_domain_slash_path_extracted(self):
        urls = _agent._find_urls("Join discord.gg/myserver now!")
        assert any("discord.gg/myserver" in u for u in urls)

    def test_no_url_returns_empty(self):
        assert _agent._find_urls("just a normal chat message") == []

    def test_exe_name_not_matched(self):
        # "discord.exe" lacks a slash after the TLD — must NOT match
        urls = _agent._find_urls("saw process discord.exe running")
        assert urls == []


class TestExtractDomain:

    def test_https_url_returns_netloc(self):
        assert _agent._extract_domain("https://discord.gg/invite") == "discord.gg"

    def test_http_url_returns_netloc(self):
        assert _agent._extract_domain("http://t.me/xyz") == "t.me"

    def test_subdomain_preserved(self):
        assert _agent._extract_domain("https://www.youtube.com/watch?v=1") == "www.youtube.com"

    def test_bare_domain_returns_domain(self):
        domain = _agent._extract_domain("discord.gg/abc")
        assert "discord.gg" in domain

    def test_result_is_lowercase(self):
        domain = _agent._extract_domain("HTTPS://DISCORD.GG/abc")
        assert domain == domain.lower()


class TestExtractContext:

    def test_url_in_middle_returns_n_lines_around_it(self):
        lines = ["line0", "line1", "line2 https://x.com/a", "line3", "line4"]
        text = "\n".join(lines)
        ctx = _agent._extract_context(text, "https://x.com/a", n=2)
        assert "https://x.com/a" in ctx

    def test_url_at_start_does_not_go_negative(self):
        text = "https://x.com/a\nline1\nline2\nline3"
        ctx = _agent._extract_context(text, "https://x.com/a", n=4)
        assert ctx  # should not raise

    def test_url_at_end_does_not_exceed_bounds(self):
        text = "line0\nline1\nhttps://x.com/a"
        ctx = _agent._extract_context(text, "https://x.com/a", n=4)
        assert "https://x.com/a" in ctx

    def test_url_not_found_returns_url_as_fallback(self):
        ctx = _agent._extract_context("no url here", "https://missing.com/x", n=5)
        assert ctx == "https://missing.com/x"

    def test_n_one_returns_containing_line(self):
        """n=1 should return exactly the line that contains the URL."""
        text = "before\nhttps://x.com/a\nafter"
        ctx = _agent._extract_context(text, "https://x.com/a", n=1)
        assert "https://x.com/a" in ctx


class TestAppMatchesUrl:

    def setup_method(self):
        """Inject a known platform map for deterministic tests."""
        self._orig = _agent._PLATFORM_APP_MAP
        _agent._PLATFORM_APP_MAP = {
            "discord": frozenset({"discord.exe"}),
            "telegram": frozenset({"telegram.exe"}),
        }

    def teardown_method(self):
        _agent._PLATFORM_APP_MAP = self._orig

    def test_matching_platform_and_process_returns_true(self):
        assert _agent._app_matches_url("https://discord.gg/abc", "discord.exe") is True

    def test_matching_platform_wrong_process_returns_false(self):
        assert _agent._app_matches_url("https://discord.gg/abc", "chrome.exe") is False

    def test_unknown_platform_returns_false(self):
        assert _agent._app_matches_url("https://unknown-site.com/x", "unknown.exe") is False

    def test_platform_keyword_in_subdomain_matches(self):
        assert _agent._app_matches_url("https://cdn.discord.com/assets", "discord.exe") is True
