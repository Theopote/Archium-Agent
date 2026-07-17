"""Application settings via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator, model_validator
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
        populate_by_name=True,
    )

    app_name: str = "Archium"
    environment: str = "development"
    log_level: str = "INFO"

    database_path: Path = Field(
        default=Path("data/database/archium.db"),
        validation_alias=AliasChoices("DATABASE_PATH"),
    )
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL"),
        description="Optional SQLAlchemy URL override. When unset, database_path is used.",
    )
    workflow_checkpoint_path: Path = Path("data/database/workflow_checkpoints.db")
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
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_repair_attempts: int = Field(default=2, ge=0, le=5)
    llm_timeout_seconds: float = Field(default=60.0, gt=0)

    embedding_provider: str = "openai_compatible"
    embedding_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_API_KEY"),
    )
    embedding_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_BASE_URL"),
    )
    embedding_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_MODEL"),
    )
    embedding_dimensions: int | None = Field(
        default=None,
        ge=1,
        validation_alias=AliasChoices("EMBEDDING_DIMENSIONS"),
    )

    retrieval_enabled: bool = False
    retrieval_top_k: int = Field(default=12, ge=1, le=50)
    chunk_context_max_chars: int = Field(default=600, ge=100, le=2000)

    embedding_chunking_enabled: bool = True
    embedding_chunk_min_segment_chars: int = Field(default=1200, ge=400, le=8000)
    embedding_breakpoint_threshold: float = Field(default=0.65, ge=0.0, le=1.0)

    semantic_chunking_enabled: bool = True
    chunk_max_chars: int = Field(default=800, ge=100, le=4000)
    chunk_min_chars: int = Field(default=80, ge=1, le=500)
    chunk_overlap_chars: int = Field(default=120, ge=0, le=500)

    marp_command: str = "marp"

    block_export_on_critical_review: bool = Field(
        default=False,
        description="When true, open CRITICAL ReviewIssue records block JSON/Marp export.",
    )
    llm_professional_review_enabled: bool = Field(
        default=False,
        description="When true and LLM is configured, run an additional LLM professional review pass.",
    )
    fact_extraction_enabled: bool = Field(
        default=True,
        description="When true and LLM is available, extract ProjectFact records after context retrieval.",
    )
    slide_repair_enabled: bool = Field(
        default=False,
        description="When true and LLM is available, auto-repair slide-level CRITICAL/HIGH review issues.",
    )

    discord_bot_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DISCORD_BOT_TOKEN"),
    )
    discord_user_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DISCORD_USER_ID"),
    )

    @model_validator(mode="after")
    def _validate_chunk_settings(self) -> Settings:
        if self.chunk_overlap_chars >= self.chunk_max_chars:
            raise ValueError("chunk_overlap_chars must be smaller than chunk_max_chars")
        if self.chunk_min_chars > self.chunk_max_chars:
            raise ValueError("chunk_min_chars must not exceed chunk_max_chars")
        if self.retrieval_enabled and not self.embedding_configured:
            self.retrieval_enabled = False
        return self

    @field_validator(
        "database_path",
        "project_storage_path",
        "output_path",
        "chroma_path",
        "workflow_checkpoint_path",
        mode="after",
    )
    @classmethod
    def _resolve_relative_paths(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return (_PROJECT_ROOT / value).resolve()

    @property
    def resolved_database_url(self) -> str:
        """Return a stable SQLAlchemy URL independent of process working directory."""
        if self.database_url:
            return self._normalize_database_url(self.database_url)
        return f"sqlite:///{self.database_path.as_posix()}"

    @staticmethod
    def _normalize_database_url(url: str) -> str:
        if not url.startswith("sqlite:///"):
            return url
        if url.startswith("sqlite:////") or url == "sqlite:///:memory:":
            return url
        path_part = url.removeprefix("sqlite:///")
        if Path(path_part).is_absolute():
            return url
        resolved = (_PROJECT_ROOT / path_part).resolve()
        return f"sqlite:///{resolved.as_posix()}"

    def ensure_directories(self) -> None:
        """Create data directories if they do not exist."""
        for path in (
            self.project_storage_path,
            self.output_path,
            self.chroma_path,
            self.workflow_checkpoint_path.parent,
            self.database_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def llm_configured(self) -> bool:
        """Return True when an LLM API key is available."""
        return bool(self.llm_api_key)

    @property
    def effective_embedding_api_key(self) -> str | None:
        """Embedding key with optional fallback to the LLM key."""
        return self.embedding_api_key or self.llm_api_key

    @property
    def effective_embedding_base_url(self) -> str | None:
        """Embedding base URL with optional fallback to the LLM base URL."""
        return self.embedding_base_url or self.llm_base_url

    @property
    def embedding_configured(self) -> bool:
        """Return True when embeddings can run with the configured provider."""
        provider = self.embedding_provider.lower()
        if provider == "mock":
            return True
        if provider == "local":
            return bool(self.embedding_model)
        return bool(self.effective_embedding_api_key and self.embedding_model)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    settings = Settings()
    settings.ensure_directories()
    return settings


def reset_settings() -> None:
    """Clear cached settings (for tests)."""
    get_settings.cache_clear()
