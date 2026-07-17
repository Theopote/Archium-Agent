"""Application settings via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Archium application settings.

    Missing API keys do not prevent startup; LLM calls fail at runtime with
    a clear :class:`ConfigurationError`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Archium"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///data/database/archium.db"
    project_storage_path: Path = Path("data/projects")
    output_path: Path = Path("data/outputs")
    chroma_path: Path = Path("data/chroma")

    llm_provider: str = "openai_compatible"
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "GEMINI_API_KEY"),
    )
    llm_base_url: str | None = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        validation_alias=AliasChoices("LLM_BASE_URL", "GEMINI_BASE_URL"),
    )
    llm_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias=AliasChoices("LLM_MODEL", "GEMINI_MODEL"),
    )

    embedding_provider: str = "openai_compatible"
    embedding_model: str | None = None

    marp_command: str = "marp"

    discord_bot_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DISCORD_BOT_TOKEN"),
    )
    discord_user_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DISCORD_USER_ID"),
    )

    @field_validator(
        "project_storage_path",
        "output_path",
        "chroma_path",
        mode="after",
    )
    @classmethod
    def _resolve_relative_paths(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return (_PROJECT_ROOT / value).resolve()

    def ensure_directories(self) -> None:
        """Create data directories if they do not exist."""
        for path in (
            self.project_storage_path,
            self.output_path,
            self.chroma_path,
            _PROJECT_ROOT / "data" / "database",
        ):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def llm_configured(self) -> bool:
        """Return True when an LLM API key is available."""
        return bool(self.llm_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    settings = Settings()
    settings.ensure_directories()
    return settings


def reset_settings() -> None:
    """Clear cached settings (for tests)."""
    get_settings.cache_clear()
