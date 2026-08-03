"""Application API — jobs / project / documents boundary."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from archium.application.api.session import api_from_session
from archium.application.background_job_worker import BackgroundJobWorker
from archium.domain.background_job import BackgroundJobKind, BackgroundJobStatus
from archium.domain.project import Project
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.repositories import ProjectRepository


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import archium.infrastructure.database.models  # noqa: F401

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    @contextmanager
    def _get_session():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    import archium.infrastructure.database.session as session_mod

    monkeypatch.setattr(session_mod, "get_session", _get_session)

    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_jobs_api_idempotent_create(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="API Job", description=""))
    api = api_from_session(db_session)
    first = api.jobs.create(
        project.id,
        BackgroundJobKind.GENERIC,
        label="once",
        idempotency_key="k-1",
        payload={"n": 1},
    )
    second = api.jobs.create(
        project.id,
        BackgroundJobKind.GENERIC,
        label="once-again",
        idempotency_key="k-1",
        payload={"n": 2},
    )
    assert first.id == second.id
    assert second.payload.get("n") == 1


def test_jobs_api_cancel_queued(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="Cancel Q", description=""))
    api = api_from_session(db_session)
    job = api.jobs.create(project.id, BackgroundJobKind.GENERIC, label="cancellable")
    cancelled = api.jobs.cancel(job.id)
    assert cancelled is not None
    assert cancelled.status == BackgroundJobStatus.CANCELLED
    assert BackgroundJobWorker(db_session).process_once() is None


def test_jobs_api_cancel_running_cooperative(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="Cancel R", description=""))
    api = api_from_session(db_session)
    job = api.jobs.create(project.id, BackgroundJobKind.GENERIC, label="running-cancel")
    claimed = api.jobs._jobs.claim_next()
    assert claimed is not None
    assert claimed.status == BackgroundJobStatus.RUNNING
    requested = api.jobs.cancel(job.id)
    assert requested is not None
    assert requested.cancel_requested is True
    assert requested.status == BackgroundJobStatus.RUNNING
    finalized = api.jobs.cancel(job.id, message="worker ack")
    assert finalized is not None
    assert finalized.status == BackgroundJobStatus.CANCELLED


def test_jobs_api_progress_after_refresh(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="Progress", description=""))
    api = api_from_session(db_session)
    job = api.jobs.create(project.id, BackgroundJobKind.GENERIC, label="track-me")
    view = api.jobs.get_progress(job.id)
    assert view is not None
    assert view.job_id == job.id
    active = api.jobs.list_active(project.id)
    assert any(item.job_id == job.id for item in active)


def test_project_api_crud(db_session: Session) -> None:
    api = api_from_session(db_session)
    created = api.project.create("门面项目", "desc")
    got = api.project.get(created.id)
    assert got.name == "门面项目"
    listed = api.project.list()
    assert any(item.id == created.id for item in listed)
    updated = api.project.update(created.id, name="改名", description="x")
    assert updated.name == "改名"


def test_documents_api_enqueue_analyze(db_session: Session, tmp_path: Path) -> None:
    project = ProjectRepository(db_session).create(Project(name="Docs", description=""))
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")
    api = api_from_session(db_session)
    job = api.documents.enqueue_analyze(
        project.id,
        path=str(path),
        filename=path.name,
        idempotency_key="doc-1",
    )
    again = api.documents.enqueue_analyze(
        project.id,
        path=str(path),
        filename=path.name,
        idempotency_key="doc-1",
    )
    assert job.id == again.id
    assert job.kind == BackgroundJobKind.DOCUMENT_ANALYZE
