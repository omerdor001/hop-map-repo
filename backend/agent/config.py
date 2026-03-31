"""
HopMap Agent — Configuration
===============================
Imported by agent.py (runs on the kid's Windows PC).
All values are read from environment variables (with sensible defaults).

Setup:
  Copy .env.example → .env, fill in your values, then run agent.py.
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# Add backend folder to path so we can import shared_config
_backend_dir = Path(__file__).parent.resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from shared_config import PLATFORMS_DB_PATH

load_dotenv()


@dataclass
class AgentConfig:
    # Where the HopMap server is running
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")

    # Ollama model used to decide whether a detected link is a hop attempt
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    # How often (in seconds) to OCR-scan the game window for links
    scan_interval_seconds: float = float(os.getenv("SCAN_INTERVAL_SECONDS", "5"))

    # How many chat lines around a detected URL to send to Ollama for context
    context_lines: int = int(os.getenv("CONTEXT_LINES", "10"))

    # Path to the Excel file containing platform process mappings
    # Default: backend/agent/platforms_db.xlsx (relative to shared_config.py location)
    # Can be overridden with PLATFORMS_DB_PATH env var
    platforms_db_path: str = os.getenv("PLATFORMS_DB_PATH", PLATFORMS_DB_PATH)


# ── Singleton instance ────────────────────────────────────────────────────────
agent_config = AgentConfig()
