"""Tests for database session management and multi-backend settings."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from archium.config.settings import Settings
from archium.exceptions import ConfigurationError
from archium.infrastructure.database import session as db_session_mod
from archium.infrastructure.database.session import (
    close_scoped_session,
    create_engine_from_settings,
    get_session,
    reset_engine_cache,
)
from sqlalchemy import text


@pytest.fixture(autouse=True)
def _reset_db_cache() -> None:
    reset_engine_cache()
    yield
    reset_engine_cache()


def test_sqlite_engine_uses_wal_and_busy_timeout(tmp_path: Path) -> None:
    db_path = tmp_path / "wal.db"
    settings = Settings(
        _env_file=None,
        database_path=db_path,
        database_sqlite_wal_enabled=True,
        database_sqlite_busy_timeout_ms=25000,
    )
    engine = create_engine_from_settings(settings)
    with engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        busy_timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()
    assert str(journal_mode).lower() == "wal"
    assert int(busy_timeout) == 25000
    engine.dispose()


def test_postgres_url_requires_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object):
        if name in {"psycopg", "psycopg2"}:
            raise ImportError(f"No module named {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ConfigurationError, match="psycopg"):
        db_session_mod._ensure_postgres_driver("postgresql+psycopg://localhost/archium")


def test_database_backend_detection(tmp_path: Path) -> None:
    sqlite_settings = Settings(_env_file=None, database_path=tmp_path / "a.db")
    assert sqlite_settings.database_backend == "sqlite"
    assert sqlite_settings.is_sqlite is True

    pg_settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://localhost/archium",
    )
    assert pg_settings.database_backend == "postgresql"
    assert pg_settings.is_postgresql is True


def test_scoped_session_shared_in_same_thread(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, database_path=tmp_path / "scoped.db")
    monkeypatch.setattr(db_session_mod, "get_settings", lambda: settings)

    with get_session(scoped=True) as first:
        first_id = id(first)
    with get_session(scoped=True) as second:
        second_id = id(second)
    close_scoped_session()
    assert first_id == second_id


def test_independent_sessions_differ_in_same_thread(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, database_path=tmp_path / "indep.db")
    monkeypatch.setattr(db_session_mod, "get_settings", lambda: settings)

    with get_session(scoped=False) as first, get_session(scoped=False) as second:
        assert id(first) != id(second)


def test_background_thread_uses_independent_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, database_path=tmp_path / "thread.db")
    monkeypatch.setattr(db_session_mod, "get_settings", lambda: settings)
    main_id: int | None = None
    worker_id: int | None = None

    with get_session(scoped=True) as main_session:
        main_id = id(main_session)

    def worker() -> None:
        nonlocal worker_id
        with get_session(scoped=False) as worker_session:
            worker_id = id(worker_session)
        close_scoped_session()

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    close_scoped_session()

    assert main_id is not None
    assert worker_id is not None
    assert main_id != worker_id
