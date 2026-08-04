"""BackgroundJobWorker — process_once cancel cooperation."""

from __future__ import annotations

import pytest
from archium.application.api.session import api_from_session
from archium.application.background_job_worker import BackgroundJobWorker
from archium.domain.background_job import BackgroundJobKind, BackgroundJobStatus
from archium.domain.project import Project
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.repositories import ProjectRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


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


def test_worker_honors_cancel_after_dispatch(db_session: Session, monkeypatch) -> None:
    project = ProjectRepository(db_session).create(Project(name="Cancel Worker", description=""))
    api = api_from_session(db_session)
    api.jobs.create(project.id, BackgroundJobKind.GENERIC, label="dispatch-cancel")
    worker = BackgroundJobWorker(db_session)

    def _cancel_during_dispatch(job):
        api.jobs.cancel(job.id, message="user cancel")
        return {"ack": True}

    monkeypatch.setattr(worker, "_dispatch", _cancel_during_dispatch)
    out = worker.process_once()
    assert out is not None
    assert out.status == BackgroundJobStatus.CANCELLED
