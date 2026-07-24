"""SQLAlchemy engine creation and process-wide cache."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool

from archium.config.settings import Settings, get_settings
from archium.exceptions import ConfigurationError


def _ensure_postgres_driver(url: str) -> None:
    if not url.startswith("postgresql"):
        return
    try:
        import psycopg  # noqa: F401
    except ImportError:
        try:
            import psycopg2  # noqa: F401
        except ImportError as exc:
            raise ConfigurationError(
                "PostgreSQL DATABASE_URL requires psycopg (v3) or psycopg2. "
                'Install with: pip install -e ".[postgres]"'
            ) from exc


def _configure_sqlite(engine: Engine, settings: Settings) -> None:
    if engine.dialect.name != "sqlite":
        return

    busy_timeout_ms = settings.database_sqlite_busy_timeout_ms
    wal_enabled = settings.database_sqlite_wal_enabled

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        if wal_enabled:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        cursor.close()


def _sqlite_connect_args(settings: Settings) -> dict[str, Any]:
    timeout_seconds = max(settings.database_sqlite_busy_timeout_ms / 1000.0, 1.0)
    return {
        "check_same_thread": False,
        "timeout": timeout_seconds,
    }


def _postgres_engine_kwargs(settings: Settings) -> dict[str, Any]:
    return {
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_recycle": settings.database_pool_recycle_seconds,
        "pool_pre_ping": settings.database_pool_pre_ping,
    }


def create_engine_from_settings(
    settings: Settings | None = None,
    *,
    poolclass: type[Pool] | None = None,
) -> Engine:
    """Create a SQLAlchemy engine from application settings."""
    resolved = settings or get_settings()
    url = resolved.resolved_database_url
    _ensure_postgres_driver(url)

    engine_kwargs: dict[str, Any] = {}
    if poolclass is not None:
        engine_kwargs["poolclass"] = poolclass

    if url.startswith("sqlite"):
        engine_kwargs["connect_args"] = _sqlite_connect_args(resolved)
        engine_kwargs.setdefault("pool_pre_ping", True)
    else:
        engine_kwargs.update(_postgres_engine_kwargs(resolved))

    engine = create_engine(url, **engine_kwargs)
    _configure_sqlite(engine, resolved)
    return engine


@lru_cache
def get_engine() -> Engine:
    """Return a cached engine for the configured database."""
    return create_engine_from_settings()


def clear_engine_cache() -> None:
    """Clear the cached engine (for tests)."""
    get_engine.cache_clear()
