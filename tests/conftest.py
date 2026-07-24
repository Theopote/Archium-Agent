"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from archium.config.settings import Settings, reset_settings
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.session import create_engine_from_settings, reset_engine_cache
from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    """Ensure each test gets fresh settings."""
    reset_settings()
    reset_engine_cache()
    yield
    reset_settings()
    reset_engine_cache()


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Return settings pointed at a temporary data directory."""
    base = tmp_path / "archium"
    (base / "database").mkdir(parents=True)
    return Settings(
        _env_file=None,
        database_path=base / "database" / "test.db",
        workflow_checkpoint_path=base / "database" / "workflow_checkpoints.db",
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
    import archium.infrastructure.database.models  # noqa: F401

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


_TIER_MARKERS = frozenset({"unit", "integration", "e2e", "benchmark", "smoke"})

# Primary CI tier markers are assigned from path when not declared on the test module/class.
_TIER_PATH_PREFIXES: tuple[tuple[str, str], ...] = (
    ("tests/unit/", "unit"),
    ("tests/ui/", "unit"),
    ("tests/domain/", "unit"),
    ("tests/spike/", "unit"),
    ("tests/application/", "integration"),
    ("tests/integration/", "integration"),
    ("tests/benchmark/", "benchmark"),
    ("tests/e2e/", "e2e"),
    ("tests/smoke/", "smoke"),
)


def _normalize_test_path(path: Path) -> str:
    return path.as_posix()


def _tier_marker_for_path(path: Path) -> str | None:
    normalized = _normalize_test_path(path)
    for prefix, tier in _TIER_PATH_PREFIXES:
        if normalized.startswith(prefix) or f"/{prefix}" in normalized:
            return tier
    return None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config
    for item in items:
        existing = {mark.name for mark in item.iter_markers()}
        if existing & _TIER_MARKERS:
            continue
        tier = _tier_marker_for_path(item.path)
        if tier is not None:
            item.add_marker(getattr(pytest.mark, tier))


@pytest.fixture
def tmp_sqlite_engine(tmp_path: Path):
    """Provide a temporary SQLite engine for testing."""
    from sqlalchemy import create_engine

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    yield engine
    engine.dispose()
