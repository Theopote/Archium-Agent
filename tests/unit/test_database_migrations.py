"""Tests for database migration management."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from archium.exceptions import ConfigurationError
from archium.infrastructure.database.migrations import (
    check_migrations_on_startup,
    get_current_revision,
    get_head_revision,
    has_pending_migrations,
)
from archium.infrastructure.database.session import init_database


def test_get_head_revision() -> None:
    """Test getting the latest revision from migration scripts."""
    head = get_head_revision()
    assert head is not None
    assert isinstance(head, str)
    # Should be in format like "011_visual_composition"
    assert len(head) > 0


def test_get_current_revision_empty_db(tmp_sqlite_engine) -> None:
    """Test get_current_revision on a brand new database."""
    # Brand new database has no alembic_version table
    revision = get_current_revision()
    assert revision is None


def test_has_pending_migrations_new_db() -> None:
    """Test has_pending_migrations on a new database."""
    # New database should report pending migrations
    assert has_pending_migrations() is True


def test_init_database_creates_tables(tmp_sqlite_engine) -> None:
    """Test that init_database creates necessary tables."""
    init_database(tmp_sqlite_engine)

    # Check that tables were created
    with tmp_sqlite_engine.connect() as conn:
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tables = {row[0] for row in result}

    # Check for key tables
    expected_tables = {
        "projects",
        "source_documents",
        "presentations",
        "slides",
        "alembic_version",
    }
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"


def test_check_migrations_on_startup_with_pending_raises(tmp_sqlite_engine) -> None:
    """Test that check_migrations_on_startup raises when migrations are pending."""
    # Initialize database with tables but not migrations
    from archium.infrastructure.database.base import Base
    from archium.infrastructure.database.models import ProjectORM  # noqa: F401

    Base.metadata.create_all(tmp_sqlite_engine)

    # Manually create alembic_version with old revision
    with tmp_sqlite_engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32))"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('001_initial')"))
        conn.commit()

    # Should raise because current != head
    with pytest.raises(ConfigurationError, match="pending migrations"):
        check_migrations_on_startup()


def test_migration_idempotency(tmp_sqlite_engine) -> None:
    """Test that running migrations multiple times is safe."""
    init_database(tmp_sqlite_engine)

    # Running again should not fail
    init_database(tmp_sqlite_engine)

    # Should still have valid revision
    revision = get_current_revision()
    assert revision is not None
