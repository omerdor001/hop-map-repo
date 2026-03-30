"""
HopMap Server — Configuration
================================
Imported by server.py and db.py.
All values are read from environment variables (with sensible defaults).

Setup:
  Copy .env.example → .env, fill in your values, then run server.py.

To switch between local MongoDB (Compass) and Atlas, change MONGO_URI only.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ServerConfig:
    # Network
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    # Database
    # Local Compass  → mongodb://localhost:27017
    # Atlas cloud    → mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/...
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name: str = os.getenv("DB_NAME", "hopmap")

    # Collections
    events_collection: str = os.getenv("EVENTS_COLLECTION", "events")
    rules_collection: str = os.getenv("RULES_COLLECTION", "rules")

    # Ollama model used server-side to classify hop attempts
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    # Path to the Excel file containing blocked words (nasty words database)
    # Excel should have a column header "word" with words to flag
    # Example: C:\Users\alex\Documents\nasty_words.xlsx
    words_db_path: str = os.getenv("WORDS_DB_PATH", "")

    # LLM provider backend.  Currently supported: "ollama"
    # Switch by setting LLM_PROVIDER=<name> in .env once a new provider is
    # added to backend/server/llm/__init__.py.
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")

    # CORS — comma-separated list of allowed origins, or "*" for all
    # Example: "http://localhost:5173,https://hopmap.vercel.app"
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "*").split(",")
    )


# ── Singleton instance ────────────────────────────────────────────────────────
# Import this directly:
#   from config import server_config

server_config = ServerConfig()
