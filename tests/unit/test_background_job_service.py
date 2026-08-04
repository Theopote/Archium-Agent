"""BackgroundJobService — claim / complete / cancel (not via JobsApi._jobs)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from archium.application.background_job_service import BackgroundJobService
from archium.domain.background_job import BackgroundJobKind, BackgroundJobStatus
from archium.domain.project import Project
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.repositories import ProjectRepository


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import archium.infrastructure.database.models  # noqa: F401

    Base.metadata.create_all(engine)
    session = Session(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_claim_next_after_queued_cancel_returns_none(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="Svc Cancel Q", description=""))
    jobs = BackgroundJobService(db_session)
    job = jobs.enqueue(project.id, BackgroundJobKind.GENERIC, label="cancellable")
    cancelled = jobs.cancel(job.id)
    assert cancelled is not None
    assert cancelled.status == BackgroundJobStatus.CANCELLED
    assert jobs.claim_next() is None


def test_cancel_running_is_cooperative(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="Svc Cancel R", description=""))
    jobs = BackgroundJobService(db_session)
    job = jobs.enqueue(project.id, BackgroundJobKind.GENERIC, label="running-cancel")
    claimed = jobs.claim_next()
    assert claimed is not None
    assert claimed.status == BackgroundJobStatus.RUNNING
    requested = jobs.cancel(job.id)
    assert requested is not None
    assert requested.cancel_requested is True
    assert requested.status == BackgroundJobStatus.RUNNING
    finalized = jobs.cancel(job.id, message="worker ack")
    assert finalized is not None
    assert finalized.status == BackgroundJobStatus.CANCELLED


def test_complete_honors_cancel_request(db_session: Session) -> None:
    """Cancel mid-run must win over a subsequent complete()."""
    project = ProjectRepository(db_session).create(Project(name="Svc Race", description=""))
    jobs = BackgroundJobService(db_session)
    job = jobs.enqueue(project.id, BackgroundJobKind.GENERIC, label="race")
    claimed = jobs.claim_next()
    assert claimed is not None
    jobs.cancel(job.id)
    finished = jobs.complete(job.id, result={"pptx": "should-not-publish"})
    assert finished is not None
    assert finished.status == BackgroundJobStatus.CANCELLED
    assert not (finished.result or {}).get("pptx")
