"""Shared test constants and utility functions for all HopMap server tests."""

import socket

# ---------------------------------------------------------------------------
# Server coordinates
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Port utility
# ---------------------------------------------------------------------------

def find_free_port() -> int:
    """Return an available localhost port for test servers."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        return s.getsockname()[1]

# ---------------------------------------------------------------------------
# Test data constants
# ---------------------------------------------------------------------------

# Words that must be present in the real words DB (hopmap_words_db.xlsx)
BLOCKED_WORD_HACK    = "hack"
BLOCKED_WORD_18PLUS  = "18+"

# Phrases that contain no blocked words
CLEAN_PHRASE         = "hey bro come check this cool server"
# Phrase that contains a blocked word
BLOCKED_PHRASE_HACK  = "click here to hack your friends account"
BLOCKED_PHRASE_HBW   = "this message has hack blocked word"

# URL stubs used across tests
SUSPICIOUS_URL       = "example.com/suspicious"
PLAIN_URL            = "example.com/page"
