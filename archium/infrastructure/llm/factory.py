"""LLM provider factory."""

from __future__ import annotations

from collections.abc import Callable

from archium.config.settings import Settings, get_settings
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.llm.mock import MockLLMProvider

EffectiveSettingsProvider = Callable[[], Settings]

_effective_settings_provider: EffectiveSettingsProvider | None = None


def set_effective_settings_provider(provider: EffectiveSettingsProvider | None) -> None:
    """Register composition-root resolver (UI / application) for bare factory calls.

    Infrastructure must not import application or UI to resolve LLM profiles.
    """
    global _effective_settings_provider
    _effective_settings_provider = provider


def get_effective_settings_provider() -> EffectiveSettingsProvider | None:
    return _effective_settings_provider


def _resolve_provider_settings(settings: Settings | None) -> Settings:
    """Resolve LLM settings from explicit override or registered provider."""
    if settings is not None:
        return settings
    if _effective_settings_provider is not None:
        return _effective_settings_provider()
    return get_settings()


def create_llm_provider(
    settings: Settings | None = None,
    *,
    provider: str | None = None,
) -> LLMProvider:
    """Create an LLM provider based on resolved application settings."""
    resolved = _resolve_provider_settings(settings)
    name = (provider or resolved.llm_provider).lower()

    if name == "mock":
        return MockLLMProvider()

    if name in {"openai_compatible", "openai", "gemini"}:
        from archium.infrastructure.llm.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider(resolved)

    raise ValueError(f"Unknown LLM provider: {name}")


def get_llm_provider() -> LLMProvider:
    """Return an LLM provider using the current effective settings."""
    return create_llm_provider()


def reset_llm_provider_cache() -> None:
    """Backward-compatible no-op; providers are created per call."""
