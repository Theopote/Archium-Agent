"""Unit tests for LLM provider factory settings resolution."""

from __future__ import annotations

from unittest.mock import patch

from archium.config.settings import Settings
from archium.infrastructure.llm.factory import (
    create_llm_provider,
    set_effective_settings_provider,
)
from archium.infrastructure.llm.mock import MockLLMProvider


def test_create_llm_provider_uses_explicit_settings() -> None:
    settings = Settings(_env_file=None, llm_provider="mock")
    provider = create_llm_provider(settings)
    assert isinstance(provider, MockLLMProvider)


def test_create_llm_provider_falls_back_to_effective_settings() -> None:
    effective = Settings(_env_file=None, llm_api_key="keyring-key", llm_provider="openai_compatible")
    with patch("archium.infrastructure.llm.factory._resolve_provider_settings", return_value=effective):
        provider = create_llm_provider()
    assert provider._settings.llm_api_key == "keyring-key"  # type: ignore[attr-defined]


def test_resolve_provider_settings_uses_registered_effective_provider() -> None:
    from archium.infrastructure.llm import factory

    ui_settings = Settings(_env_file=None, llm_api_key="ui-api-key")
    set_effective_settings_provider(lambda: ui_settings)
    try:
        resolved = factory._resolve_provider_settings(None)
        assert resolved.llm_api_key == "ui-api-key"
    finally:
        set_effective_settings_provider(None)
