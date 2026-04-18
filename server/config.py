"""
HopMap Server — Configuration
===============================
Layered configuration (highest priority wins):
  1. Environment variables / .env  ← secrets and machine-specific overrides
  2. server_config.json            ← operational defaults (committed to repo)
  3. Field defaults                ← fallback hard-coded values

Only secrets (e.g. HOPMAP_SERVER__DB__MONGO_URI) belong in .env.
Everything else lives in server_config.json.

Setup:
  Edit server_config.json for your deployment, then add a .env with secrets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

_DATA_DIR = Path(__file__).parent.resolve() / "data"
_CONFIG_FILE = Path(__file__).parent.resolve() / "server_config.json"


class NetworkConfig(BaseModel):
    """HTTP server binding."""

    host: str = Field("0.0.0.0", description="Bind address")
    port: int = Field(8000, description="Listen port", ge=1, le=65535)
    # Comma-separated list of allowed CORS origins, or "*" for all.
    # Example: "http://localhost:5173,https://hopmap.vercel.app"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


class DatabaseConfig(BaseModel):
    """MongoDB connection."""

    # Local Compass  → mongodb://localhost:27017
    # Atlas cloud    → mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/...
    mongo_uri: str = Field("mongodb://localhost:27017", description="MongoDB connection URI")
    db_name: str = Field("hopmap", description="Database name")
    events_collection: str = Field("events", description="Events collection name")
    rules_collection: str = Field("rules", description="Rules collection name")
    words_collection: str = Field("words", description="Blocked-words collection name")
    words_refresh_interval_seconds: int = Field(
        3600, description="How often (seconds) to reload blocked words from MongoDB", gt=0
    )


class LLMConfig(BaseModel):
    """LLM inference backend."""

    # Currently supported: "ollama".
    # Add a new provider in server/llm/__init__.py, then set this env var.
    provider: str = Field("ollama", description="LLM backend provider")
    model: str = Field("qwen2.5:7b", description="Model name passed to the provider")


class AuthConfig(BaseModel):
    """JWT and session configuration."""

    jwt_secret: str = Field("change-me-in-production", description="HS256 signing secret — override via HOPMAP_SERVER__AUTH__JWT_SECRET env var")
    jwt_algorithm: str = Field("HS256", description="JWT signing algorithm")
    access_token_expire_minutes: int = Field(15, description="Access token lifetime in minutes", gt=0)
    refresh_token_expire_days: int = Field(30, description="Refresh token lifetime in days", gt=0)
    refresh_cookie_name: str = Field("hopmap_refresh", description="Name of the httpOnly refresh token cookie")
    refresh_cookie_secure: bool = Field(False, description="Set True in production (requires HTTPS)")


class DataConfig(BaseModel):
    """Paths to data files loaded at server startup."""

    words_db_path: str = Field(
        default_factory=lambda: str(_DATA_DIR / "hopmap_words_db.xlsx"),
        description="Excel file with blocked-words list (column: 'word')",
    )
    platforms_db_path: str = Field(
        default_factory=lambda: str(_DATA_DIR / "platforms_db.xlsx"),
        description="Excel file with platform→process mappings, served via GET /api/platforms",
    )


class ServerConfig(BaseSettings):
    """Root configuration for the HopMap server."""

    network: NetworkConfig = Field(default_factory=NetworkConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    data: DataConfig = Field(default_factory=DataConfig)

    # Maximum classify requests per child per minute.
    classify_max_rpm: int = Field(
        30, description="Max classify calls per child per minute", gt=0
    )

    # Expose demo-seed endpoints (development / competition demo only).
    # Set HOPMAP_SERVER__DEMO_MODE=true in .env to enable.
    demo_mode: bool = Field(False, description="Expose demo seeding endpoints")

    @field_validator("network", mode="before")
    @classmethod
    def _parse_cors(cls, v: object) -> object:
        """Allow CORS_ORIGINS as a plain comma-separated string in .env."""
        if isinstance(v, dict) and "cors_origins" in v:
            raw = v["cors_origins"]
            if isinstance(raw, str):
                v["cors_origins"] = [o.strip() for o in raw.split(",") if o.strip()]
        return v

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
        env_prefix="HOPMAP_SERVER__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# ── Singleton instance ────────────────────────────────────────────────────────
# Import this directly:  from config import server_config
config_manager = ServerConfig()
