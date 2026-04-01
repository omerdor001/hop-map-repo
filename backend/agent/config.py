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
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Allow imports from shared_config when running from subdirectory
_backend_dir = Path(__file__).parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir.parent))

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

    # Show a warning popup to the child when a hop is confirmed (grooming alert)
    enable_child_alerts: bool = os.getenv("ENABLE_CHILD_ALERTS", "true").lower() in (
        "true",
        "1",
        "yes",
    )


# ── Singleton instance ────────────────────────────────────────────────────────
agent_config = AgentConfig()
