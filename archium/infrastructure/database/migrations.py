"""Enhanced Alembic migration management with validation."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine

from archium.exceptions import ConfigurationError
from archium.logging import get_logger

logger = get_logger(__name__, operation="database")

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def get_alembic_config() -> Config:
    """Get Alembic configuration."""
    config_path = _PROJECT_ROOT / "alembic.ini"
    if not config_path.exists():
        raise ConfigurationError(f"Alembic config not found: {config_path}")
    return Config(str(config_path))


def get_current_revision(engine: Engine | None = None) -> str | None:
    """Get the current database revision."""
    from sqlalchemy import text

    from archium.infrastructure.database.session import get_engine

    target = engine or get_engine()
    with target.connect() as conn:
        # Check if alembic_version table exists
        result = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
                if target.dialect.name == "sqlite"
                else "SELECT tablename FROM pg_tables WHERE tablename='alembic_version'"
            )
        )
        if not result.fetchone():
            return None

        # Get current revision
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        row = result.fetchone()
        return row[0] if row else None


def get_head_revision() -> str | None:
    """Get the latest revision from migration scripts."""
    config = get_alembic_config()
    script = ScriptDirectory.from_config(config)
    return script.get_current_head()


def has_pending_migrations(engine: Engine | None = None) -> bool:
    """Check if there are pending migrations."""
    current = get_current_revision(engine)
    head = get_head_revision()

    if current is None:
        return True  # No migrations applied yet

    return current != head


def _configure_alembic_for_engine(config: Config, engine: Engine | None) -> None:
    if engine is None:
        return
    url = engine.url.render_as_string(hide_password=False)
    config.set_main_option("sqlalchemy.url", url)
    # env.py reads this attribute to target the passed engine instead of the
    # global settings database.
    config.attributes["engine_url"] = url


def run_pending_migrations(engine: Engine | None = None) -> None:
    """Apply pending Alembic migrations up to head."""
    try:
        config = get_alembic_config()
    except ConfigurationError as e:
        logger.warning("Cannot load Alembic config: %s", e)
        return

    _configure_alembic_for_engine(config, engine)

    current = get_current_revision(engine)
    head = get_head_revision()

    if current is None:
        logger.info("No migrations applied yet. Running all migrations to head: %s", head)
    elif current == head:
        logger.info("Database is up to date at revision: %s", current)
        return
    else:
        logger.info("Upgrading database from %s to %s", current, head)

    command.upgrade(config, "head")
    logger.info("Database migrations completed successfully")


def check_migrations_on_startup(engine: Engine | None = None) -> None:
    """Check for pending migrations on application startup.

    Raises ConfigurationError if migrations need to be applied manually.
    This prevents accidental schema drift in production environments.
    """
    if not has_pending_migrations(engine):
        logger.debug("Database schema is up to date")
        return

    current = get_current_revision(engine)
    head = get_head_revision()

    if current is None:
        # First time setup - allow automatic migration
        logger.warning(
            "Database is not initialized. Running migrations automatically. "
            "Current: None, Head: %s",
            head,
        )
        run_pending_migrations(engine)
        return

    # Database exists but has pending migrations
    raise ConfigurationError(
        f"Database has pending migrations. Current: {current}, Head: {head}. "
        "Please run: alembic upgrade head"
    )
