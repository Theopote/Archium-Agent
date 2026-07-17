"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.config.settings import Settings, reset_settings


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    """Ensure each test gets fresh settings."""
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Return settings pointed at a temporary data directory."""
    base = tmp_path / "archium"
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{base / 'database' / 'test.db'}",
        project_storage_path=base / "projects",
        output_path=base / "outputs",
        chroma_path=base / "chroma",
        llm_api_key=None,
    )
