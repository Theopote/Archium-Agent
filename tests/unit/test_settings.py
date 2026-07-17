"""Tests for application settings."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.config.settings import Settings, get_settings, reset_settings
from archium.exceptions import ConfigurationError


def test_settings_default_without_api_key() -> None:
    settings = Settings(_env_file=None, llm_api_key=None)
    assert settings.llm_api_key is None
    assert settings.llm_configured is False
    assert settings.app_name == "Archium"


def test_settings_gemini_api_key_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    reset_settings()
    settings = Settings()
    assert settings.llm_api_key == "test-key-123"
    assert settings.llm_configured is True


def test_settings_ensure_directories(tmp_path: Path) -> None:
    base = tmp_path / "data"
    settings = Settings(
        _env_file=None,
        project_storage_path=base / "projects",
        output_path=base / "outputs",
        chroma_path=base / "chroma",
    )
    settings.ensure_directories()
    assert (base / "projects").is_dir()
    assert (base / "outputs").is_dir()
    assert (base / "chroma").is_dir()


def test_get_settings_creates_data_dirs() -> None:
    reset_settings()
    settings = get_settings()
    assert settings.project_storage_path.is_dir()
    assert settings.output_path.is_dir()


def test_config_client_raises_without_api_key() -> None:
    import config

    # Force re-read with no key
    reset_settings()
    config._client = None  # noqa: SLF001
    config._settings = Settings(_env_file=None, llm_api_key=None)  # noqa: SLF001
    config.GEMINI_API_KEY = None

    with pytest.raises(ConfigurationError, match="API Key"):
        config.get_client()
