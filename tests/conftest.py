"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from archium.config.settings import Settings, reset_settings
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.session import create_engine_from_settings, reset_engine_cache
from archium.infrastructure.llm.factory import reset_llm_provider_cache
from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    """Ensure each test gets fresh settings."""
    reset_settings()
    reset_engine_cache()
    reset_llm_provider_cache()
    yield
    reset_settings()
    reset_engine_cache()
    reset_llm_provider_cache()


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Return settings pointed at a temporary data directory."""
    base = tmp_path / "archium"
    (base / "database").mkdir(parents=True)
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{base / 'database' / 'test.db'}",
        project_storage_path=base / "projects",
        output_path=base / "outputs",
        chroma_path=base / "chroma",
        llm_api_key=None,
        embedding_provider="mock",
        retrieval_enabled=True,
    )


@pytest.fixture
def db_session(test_settings: Settings) -> Generator[Session, None, None]:
    """Provide an isolated SQLite session for repository tests."""
    engine = create_engine_from_settings(test_settings)
    Base.metadata.create_all(engine)
    session = Session(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
