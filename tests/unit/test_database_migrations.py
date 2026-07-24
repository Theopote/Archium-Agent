"""Tests for database migration management."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from archium.exceptions import ConfigurationError
from archium.infrastructure.database.migrations import (
    check_migrations_on_startup,
    get_current_revision,
    get_head_revision,
    has_pending_migrations,
)
from archium.infrastructure.database.session import init_database, reset_engine_cache
from sqlalchemy import text
from sqlalchemy.engine import Engine


@pytest.fixture
def isolated_migration_engine(tmp_path: Path, monkeypatch) -> Iterator[Engine]:
    """Point migration helpers at an isolated on-disk SQLite database."""
    import archium.infrastructure.database.session as session_module
    from archium.config.settings import Settings, reset_settings
    from archium.infrastructure.database.session import create_engine_from_settings

    base = tmp_path / "migration-test"
    base.mkdir()
    settings = Settings(
        _env_file=None,
        database_path=base / "archium.db",
        workflow_checkpoint_path=base / "workflow.db",
        project_storage_path=base / "projects",
        output_path=base / "outputs",
        chroma_path=base / "chroma",
    )
    reset_engine_cache()
    reset_settings()
    monkeypatch.setattr("archium.config.settings.get_settings", lambda: settings)
    engine = create_engine_from_settings(settings)
    monkeypatch.setattr(session_module, "get_engine", lambda: engine)
    yield engine
    reset_engine_cache()


def test_get_head_revision() -> None:
    """Test getting the latest revision from migration scripts."""
    head = get_head_revision()
    assert head is not None
    assert isinstance(head, str)
    # Should be in format like "011_visual_composition"
    assert len(head) > 0


def test_get_current_revision_empty_db(isolated_migration_engine: Engine) -> None:
    """Test get_current_revision on a brand new database."""
    revision = get_current_revision()
    assert revision is None


def test_has_pending_migrations_new_db(isolated_migration_engine: Engine) -> None:
    """Test has_pending_migrations on a new database."""
    assert has_pending_migrations() is True


def test_init_database_creates_tables(isolated_migration_engine: Engine) -> None:
    """Test that init_database creates necessary tables."""
    init_database(isolated_migration_engine)

    with isolated_migration_engine.connect() as conn:
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tables = {row[0] for row in result}

    expected_tables = {
        "projects",
        "source_documents",
        "presentations",
        "slides",
        "alembic_version",
    }
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"


def test_check_migrations_on_startup_with_pending_raises(isolated_migration_engine: Engine) -> None:
    """Test that check_migrations_on_startup raises when migrations are pending."""
    from archium.infrastructure.database.base import Base
    from archium.infrastructure.database.models import ProjectORM  # noqa: F401

    Base.metadata.create_all(isolated_migration_engine)

    with isolated_migration_engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32))"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('001_initial')"))
        conn.commit()

    with pytest.raises(ConfigurationError, match="pending migrations"):
        check_migrations_on_startup(isolated_migration_engine)


def test_init_database_initializes_custom_engine_when_global_is_migrated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_database(custom_engine) must set up the passed engine, not consult global revision only."""
    from archium.config.settings import Settings, reset_settings
    from archium.infrastructure.database.session import (
        create_engine_from_settings,
        init_database,
        reset_engine_cache,
    )

    def _settings(base: Path) -> Settings:
        return Settings(
            _env_file=None,
            database_path=base / "archium.db",
            workflow_checkpoint_path=base / "workflow.db",
            project_storage_path=base / "projects",
            output_path=base / "outputs",
            chroma_path=base / "chroma",
        )

    global_base = tmp_path / "global"
    fresh_base = tmp_path / "fresh"
    global_base.mkdir()
    fresh_base.mkdir()

    global_settings = _settings(global_base)
    fresh_settings = _settings(fresh_base)

    reset_engine_cache()
    reset_settings()
    monkeypatch.setattr("archium.config.settings.get_settings", lambda: global_settings)
    monkeypatch.setattr(
        "archium.infrastructure.database.session.get_settings",
        lambda: global_settings,
    )

    global_engine = create_engine_from_settings(global_settings)
    init_database(global_engine)
    assert get_current_revision(global_engine) is not None

    fresh_engine = create_engine_from_settings(fresh_settings)
    assert get_current_revision(fresh_engine) is None

    # Do not patch get_engine to fresh_engine — reproduces the historical bug.
    init_database(fresh_engine)

    with fresh_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'"
            )
        )
        assert result.fetchone() is not None

    reset_engine_cache()


def test_get_current_revision_accepts_explicit_engine(isolated_migration_engine: Engine) -> None:
    assert get_current_revision(isolated_migration_engine) is None


def test_migration_idempotency(isolated_migration_engine: Engine) -> None:
    """Test that running migrations multiple times is safe."""
    init_database(isolated_migration_engine)
    init_database(isolated_migration_engine)

    revision = get_current_revision()
    assert revision is not None
