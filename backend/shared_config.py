"""
HopMap Shared Configuration
=============================
Shared config for both server and agent.
Paths are resolved from .env or fall back to relative paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Get the directory where this config file is located
CONFIG_DIR = Path(__file__).parent.resolve()

# Load .env from the backend folder (can be overridden by individual .env files)
load_dotenv(CONFIG_DIR / ".env")


def _resolve_path(env_var: str, default_relative: str) -> str:
    """Resolve path from env var, or fall back to relative path from config location."""
    # First check environment variable
    env_value = os.getenv(env_var)
    if env_value:
        # If it's an absolute path, use it as-is
        if os.path.isabs(env_value):
            return env_value
        # Otherwise resolve relative to config location
        return str(CONFIG_DIR / env_value)

    # Fall back to default relative path
    return str(CONFIG_DIR / default_relative)


# ── Shared Paths ───────────────────────────────────────────────────────────────

# Nasty words database (Excel file with "word" column)
# Set WORDS_DB_PATH in .env to override, or leave empty to use default
# Default: backend/server/hopmap_words_db.xlsx
WORDS_DB_PATH = _resolve_path("WORDS_DB_PATH", "server/hopmap_words_db.xlsx")

# Platform process mappings (Excel file with "platform" and "process" columns)
# Set PLATFORMS_DB_PATH in .env to override, or leave empty to use default
# Default: backend/agent/platforms_db.xlsx
PLATFORMS_DB_PATH = _resolve_path("PLATFORMS_DB_PATH", "agent/platforms_db.xlsx")
