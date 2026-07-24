"""LLM provider factory."""

from __future__ import annotations

from archium.config.settings import Settings
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.llm.mock import MockLLMProvider


def _resolve_provider_settings(settings: Settings | None) -> Settings:
    """Resolve LLM settings from explicit override, UI session, keyring, or env."""
    if settings is not None:
        return settings
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx() is not None:
            from archium.ui.llm_settings import get_ui_effective_settings

            return get_ui_effective_settings()
    except Exception:
        pass
    from archium.config.llm_config import get_effective_settings

    return get_effective_settings()


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
