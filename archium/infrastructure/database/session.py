"""Database session management.

Commit ownership (APP-003 / DB-005)
---------------------------------
* :func:`get_session` is the default transaction boundary: commit on success
  exit, rollback on exception. Repositories flush only.
* UI must not call ``session.commit()``; rely on this boundary (or an
  application use-case service that owns the commit).
* Nested application helpers and infrastructure must flush only — never commit.
* Allowed mid-session commits (use-case / visibility exceptions):
  - ``TransactionExecutor`` success path (atomic visual edit)
  - ``commit_workflow_checkpoint`` when the setting is enabled (cross-session poll)
  - ``ProjectDeletionService`` staged delete protocol
  - ``ProjectManagementService`` CRUD use-case entry points
"""

from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager, suppress

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from archium.infrastructure.database.engine import (
    clear_engine_cache,
    create_engine_from_settings,
    get_engine,
)

_scoped_session_factory: scoped_session[Session] | None = None
_session_factory: sessionmaker[Session] | None = None
_scoped_lock = threading.Lock()

__all__ = [
    "close_scoped_session",
    "create_engine_from_settings",
    "get_engine",
    "get_session",
    "get_session_factory",
    "init_database",
    "reset_engine_cache",
]


def _is_streamlit_script_thread() -> bool:
    """True when running inside an active Streamlit script rerun (main UI thread)."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


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
    """Initialize database schema via Alembic only (DB-002).

    Cold databases run ``alembic upgrade head`` (revision 001 creates the
    SQLAlchemy metadata baseline). Existing databases still require pending
    migrations to be applied explicitly when the revision lags behind head.
    """
    import archium.infrastructure.database.models  # noqa: F401

    target = engine or get_engine()

    from archium.infrastructure.database.migrations import check_migrations_on_startup

    check_migrations_on_startup(engine=target)


def reset_engine_cache() -> None:
    """Clear cached engine and session factories (for tests)."""
    global _scoped_session_factory, _session_factory
    clear_engine_cache()
    if _scoped_session_factory is not None:
        with suppress(Exception):
            _scoped_session_factory.remove()
        _scoped_session_factory = None
    _session_factory = None
