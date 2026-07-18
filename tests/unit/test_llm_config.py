"""Unit tests for effective LLM settings resolution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from archium.config.llm_config import get_effective_settings
from archium.config.settings import Settings
from archium.domain.llm_profile import LLMProfile
from archium.infrastructure.credentials.resolver import resolve_llm_api_key


def _profile(**overrides: object) -> LLMProfile:
    base = {
        "provider": "gemini",
        "base_url": "https://example.test/v1/",
        "model": "test-model",
        "credential_key": "archium.llm.profile.default",
    }
    base.update(overrides)
    return LLMProfile.model_validate(base)


def test_resolve_api_key_priority_session_over_keyring_over_env() -> None:
    profile = _profile()
    store = MagicMock()
    store.get.return_value = "keyring-key"

    key, source = resolve_llm_api_key(
        profile,
        session_api_key="session-key",
        env_api_key="env-key",
        credential_store=store,
    )
    assert key == "session-key"
    assert source == "session"
    store.get.assert_not_called()

    key, source = resolve_llm_api_key(
        profile,
        env_api_key="env-key",
        credential_store=store,
    )
    assert key == "keyring-key"
    assert source == "keyring"

    store.get.return_value = None
    key, source = resolve_llm_api_key(
        profile,
        env_api_key="env-key",
        credential_store=store,
    )
    assert key == "env-key"
    assert source == "env"


def test_get_effective_settings_applies_profile_and_session_key() -> None:
    profile = _profile(model="resolved-model", base_url="https://resolved.test/v1/")
    base = Settings(_env_file=None, llm_api_key="env-key", llm_model="env-model")
    store = MagicMock()
    store.get.return_value = None

    effective = get_effective_settings(
        session_api_key="session-key",
        base_settings=base,
        profile=profile,
        credential_store=store,
    )

    assert effective.llm_api_key == "session-key"
    assert effective.llm_model == "resolved-model"
    assert effective.llm_base_url == "https://resolved.test/v1/"


def test_get_effective_settings_loads_profile_from_database() -> None:
    profile = _profile(id=uuid4(), model="db-model")
    base = Settings(_env_file=None)

    mock_service = MagicMock()
    mock_service.get_default_profile.return_value = profile

    store = MagicMock()
    store.get.return_value = "stored-key"

    with patch("archium.config.llm_config.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = MagicMock()
        with patch("archium.config.llm_config.LLMProfileService", return_value=mock_service):
            effective = get_effective_settings(
                base_settings=base,
                credential_store=store,
            )

    assert effective.llm_api_key == "stored-key"
    assert effective.llm_model == "db-model"
