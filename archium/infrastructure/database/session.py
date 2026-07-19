"""Database session and engine management."""

from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager, suppress
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from sqlalchemy.pool import Pool

from archium.config.settings import Settings, get_settings
from archium.exceptions import ConfigurationError
from archium.infrastructure.database.base import Base

_scoped_session_factory: scoped_session[Session] | None = None
_session_factory: sessionmaker[Session] | None = None
_scoped_lock = threading.Lock()


def _is_streamlit_script_thread() -> bool:
    """True when running inside an active Streamlit script rerun (main UI thread)."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


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


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Return a session factory bound to the given or default engine."""
    global _session_factory
    bind = engine or get_engine()
    if engine is None and _session_factory is not None:
        return _session_factory
    factory = sessionmaker(bind=bind, autoflush=False, autocommit=False, expire_on_commit=False)
    if engine is None:
        _session_factory = factory
    return factory


def _get_scoped_session_factory() -> scoped_session[Session]:
    global _scoped_session_factory
    if _scoped_session_factory is None:
        with _scoped_lock:
            if _scoped_session_factory is None:
                _scoped_session_factory = scoped_session(
                    get_session_factory(),
                    scopefunc=threading.get_ident,
                )
    return _scoped_session_factory


def close_scoped_session() -> None:
    """Remove and close the thread-local scoped session (Streamlit rerun cleanup)."""
    global _scoped_session_factory
    if _scoped_session_factory is None:
        return
    _scoped_session_factory.remove()


@contextmanager
def _independent_session(engine: Engine | None = None) -> Generator[Session, None, None]:
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


@contextmanager
def _scoped_request_session() -> Generator[Session, None, None]:
    session = _get_scoped_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise


@contextmanager
def get_session(
    engine: Engine | None = None,
    *,
    scoped: bool | None = None,
) -> Generator[Session, None, None]:
    """Provide a transactional database session.

    When ``scoped`` is True (or auto-detected in Streamlit UI threads), returns the
    thread-local scoped session shared for the current rerun. Call
    :func:`close_scoped_session` at the end of the Streamlit script.

    Background worker threads and explicit ``engine=`` always receive an independent
    session that is closed when the context exits.
    """
    use_scoped = scoped if scoped is not None else _is_streamlit_script_thread()
    if engine is not None:
        use_scoped = False

    if use_scoped:
        with _scoped_request_session() as session:
            yield session
    else:
        with _independent_session(engine) as session:
            yield session


def init_database(engine: Engine | None = None) -> None:
    """Create all database tables and apply pending schema migrations."""
    import archium.infrastructure.database.models  # noqa: F401

    target = engine or get_engine()
    Base.metadata.create_all(target)
    if engine is None:
        from archium.infrastructure.database.migrations import run_pending_migrations

        run_pending_migrations()


def reset_engine_cache() -> None:
    """Clear cached engine and session factories (for tests)."""
    global _scoped_session_factory, _session_factory
    get_engine.cache_clear()
    if _scoped_session_factory is not None:
        with suppress(Exception):
            _scoped_session_factory.remove()
        _scoped_session_factory = None
    _session_factory = None
