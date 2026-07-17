"""Unit tests for Settings path and embedding configuration."""

from __future__ import annotations

import os
from pathlib import Path

from archium.config.settings import Settings, reset_settings


def test_resolved_database_url_is_absolute(tmp_path: Path, monkeypatch: os._Environ) -> None:
    reset_settings()
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None, database_path=Path("data/database/archium.db"))
    db_file = Path(settings.resolved_database_url.removeprefix("sqlite:///"))
    assert db_file.is_absolute()


def test_database_url_override_is_normalized(tmp_path: Path, monkeypatch: os._Environ) -> None:
    reset_settings()
    monkeypatch.chdir(tmp_path)
    project_root = Path(__file__).resolve().parents[2]
    settings = Settings(
        _env_file=None,
        database_url="sqlite:///data/database/custom.db",
    )
    assert settings.resolved_database_url == (
        f"sqlite:///{(project_root / 'data/database/custom.db').resolve().as_posix()}"
    )


def test_embedding_configured_requires_model_for_remote_provider() -> None:
    settings = Settings(
        _env_file=None,
        embedding_provider="openai_compatible",
        embedding_api_key="test-key",
        embedding_model=None,
    )
    assert settings.embedding_configured is False

    configured = Settings(
        _env_file=None,
        embedding_provider="openai_compatible",
        embedding_api_key="test-key",
        embedding_model="text-embedding-3-small",
    )
    assert configured.embedding_configured is True


def test_retrieval_disabled_when_embedding_unconfigured() -> None:
    settings = Settings(
        _env_file=None,
        retrieval_enabled=True,
        embedding_provider="openai_compatible",
        embedding_model=None,
    )
    assert settings.retrieval_enabled is False


def test_mock_embedding_provider_is_configured() -> None:
    settings = Settings(_env_file=None, embedding_provider="mock")
    assert settings.embedding_configured is True
