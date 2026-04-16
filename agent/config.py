"""
HopMap Agent — Configuration
===============================
Layered configuration (highest priority wins):
  1. Environment variables / .env  ← machine-specific overrides
  2. agent_config.json             ← operational defaults (committed to repo)
  3. Field defaults                ← fallback hard-coded values

agent_config.json holds deployment settings (backend_url, scan tuning).
.env is for any per-machine overrides that shouldn't be in the repo.

Setup:
  Edit agent_config.json (set backend_url to the server's address),
  then run agent.py.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

_CONFIG_FILE = Path(__file__).parent.resolve() / "agent_config.json"


class AgentConfig(BaseSettings):
    """Runtime configuration for the HopMap desktop agent."""

    # Where the HopMap server is running.
    backend_url: str = Field("http://localhost:8000", description="HopMap server base URL")

    # Ollama model used to decide whether a detected link is a hop attempt.
    ollama_model: str = Field("qwen2.5:7b", description="Ollama model for hop classification")

    # How often (in seconds) to OCR-scan the game window for links.
    scan_interval_seconds: float = Field(5.0, description="OCR scan interval in seconds", gt=0)

    # How many chat lines around a detected URL to send to Ollama for context.
    context_lines: int = Field(10, description="Context lines sent with each classification request", ge=1)

    @field_validator("backend_url", mode="after")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Priority (first = highest): init > env vars > .env file > JSON config > defaults
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            JsonConfigSettingsSource(settings_cls, json_file=_CONFIG_FILE),
        )

    model_config = SettingsConfigDict(
        env_prefix="HOPMAP_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# ── Singleton instance ────────────────────────────────────────────────────────
# Import this directly:  from config import agent_config
config_manager = AgentConfig()
