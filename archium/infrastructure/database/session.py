"""Database session and engine management."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from archium.config.settings import Settings, get_settings
from archium.infrastructure.database.base import Base


def _configure_sqlite(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_engine_from_settings(settings: Settings | None = None) -> Engine:
    """Create a SQLAlchemy engine from application settings."""
    settings = settings or get_settings()
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
        pool_pre_ping=True,
    )
    _configure_sqlite(engine)
    return engine


@lru_cache
def get_engine() -> Engine:
    """Return a cached engine for the configured database."""
    return create_engine_from_settings()


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Return a session factory bound to the given or default engine."""
    bind = engine or get_engine()
    return sessionmaker(bind=bind, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def get_session(engine: Engine | None = None) -> Generator[Session, None, None]:
    """Provide a transactional database session."""
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database(engine: Engine | None = None) -> None:
    """Create all database tables."""
    import archium.infrastructure.database.models  # noqa: F401

    target = engine or get_engine()
    Base.metadata.create_all(target)


def reset_engine_cache() -> None:
    """Clear cached engine (for tests)."""
    get_engine.cache_clear()
