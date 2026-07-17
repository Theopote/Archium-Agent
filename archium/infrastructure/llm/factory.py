"""LLM provider factory."""

from __future__ import annotations

from functools import lru_cache

from archium.config.settings import Settings, get_settings
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.llm.mock import MockLLMProvider
from archium.infrastructure.llm.openai_compatible import OpenAICompatibleProvider


def create_llm_provider(
    settings: Settings | None = None,
    *,
    provider: str | None = None,
) -> LLMProvider:
    """Create an LLM provider based on settings."""
    settings = settings or get_settings()
    name = (provider or settings.llm_provider).lower()

    if name == "mock":
        return MockLLMProvider()

    if name in {"openai_compatible", "openai", "gemini"}:
        return OpenAICompatibleProvider(settings)

    raise ValueError(f"Unknown LLM provider: {name}")


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Return a cached default LLM provider."""
    return create_llm_provider()


def reset_llm_provider_cache() -> None:
    """Clear cached provider (for tests)."""
    get_llm_provider.cache_clear()
