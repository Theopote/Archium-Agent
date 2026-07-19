"""Tests for settings and configuration management."""

from __future__ import annotations

import pytest
from archium.config.settings import Settings
from pydantic import ValidationError


def test_settings_defaults() -> None:
    """Test default settings values."""
    settings = Settings(_env_file=None)

    assert settings.app_name == "Archium"
    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.llm_provider == "openai_compatible"
    assert settings.llm_max_retries == 2
    assert settings.retrieval_enabled is False
    assert settings.chunk_max_chars == 800


def test_settings_resource_limits() -> None:
    """Test new resource limit configurations."""
    settings = Settings(_env_file=None)

    # LLM concurrency limit
    assert settings.llm_max_concurrent_requests == 5
    assert 1 <= settings.llm_max_concurrent_requests <= 20

    # ChromaDB limit
    assert settings.chroma_max_documents == 10000
    assert settings.chroma_max_documents >= 100

    # Checkpoint retention
    assert settings.workflow_checkpoint_retention_days == 7
    assert 1 <= settings.workflow_checkpoint_retention_days <= 90


def test_settings_custom_resource_limits() -> None:
    """Test custom resource limit values."""
    settings = Settings(
        _env_file=None,
        llm_max_concurrent_requests=10,
        chroma_max_documents=5000,
        workflow_checkpoint_retention_days=30,
    )

    assert settings.llm_max_concurrent_requests == 10
    assert settings.chroma_max_documents == 5000
    assert settings.workflow_checkpoint_retention_days == 30


def test_settings_llm_configured() -> None:
    """Test llm_configured property."""
    # Without API key
    settings = Settings(_env_file=None, llm_api_key=None)
    assert settings.llm_configured is False

    # With API key
    settings = Settings(_env_file=None, llm_api_key="test-key")
    assert settings.llm_configured is True


def test_settings_embedding_api_key_fallback() -> None:
    """Test embedding API key falls back to LLM key."""
    settings = Settings(
        _env_file=None,
        llm_api_key="llm-key",
        embedding_api_key=None,
    )

    assert settings.effective_embedding_api_key == "llm-key"

    # With explicit embedding key
    settings = Settings(
        _env_file=None,
        llm_api_key="llm-key",
        embedding_api_key="embedding-key",
    )

    assert settings.effective_embedding_api_key == "embedding-key"


def test_settings_database_url_override() -> None:
    """Test database_url overrides database_path."""
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@host/db",
    )

    assert "postgresql" in settings.resolved_database_url


def test_settings_validation_constraints() -> None:
    """Test settings validation constraints."""
    # Invalid values should raise validation errors
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_max_concurrent_requests=0)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, chroma_max_documents=50)  # Below minimum

    with pytest.raises(ValidationError):
        Settings(_env_file=None, workflow_checkpoint_retention_days=0)


def test_settings_retrieval_configured() -> None:
    """Test retrieval_configured property."""
    # Disabled explicitly
    settings = Settings(_env_file=None, retrieval_enabled=False)
    assert settings.retrieval_configured is False

    # Enabled but no embedding config
    settings = Settings(
        _env_file=None,
        retrieval_enabled=True,
        embedding_api_key=None,
        embedding_model=None,
    )
    assert settings.retrieval_configured is False

    # Enabled with embedding config
    settings = Settings(
        _env_file=None,
        retrieval_enabled=True,
        embedding_api_key="key",
        embedding_model="text-embedding-3-small",
    )
    assert settings.retrieval_configured is True
