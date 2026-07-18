"""LLM configuration profile (non-secret settings)."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel

DEFAULT_CREDENTIAL_KEY = "archium.llm.profile.default"
DEFAULT_PROFILE_NAME = "默认配置"


class LLMProfile(IdentifiedModel, TimestampedModel):
    """Public LLM settings stored in the database; API keys live in the credential store."""

    name: str = Field(default=DEFAULT_PROFILE_NAME, min_length=1, max_length=120)
    provider: str = Field(default="gemini", min_length=1, max_length=40)
    base_url: str | None = None
    model: str = Field(default="gemini-2.5-flash", min_length=1, max_length=120)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=60.0, gt=0, le=600.0)
    credential_key: str = Field(default=DEFAULT_CREDENTIAL_KEY, min_length=1, max_length=200)

    @property
    def llm_provider(self) -> str:
        """Map UI provider slug to the internal factory provider name."""
        return "openai_compatible"
