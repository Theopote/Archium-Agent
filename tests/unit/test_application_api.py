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


def test_ingest_enqueues_analyze_job(db_session: Session, tmp_path: Path) -> None:
    from archium.application.ingestion_service import IngestionService

    project = ProjectRepository(db_session).create(Project(name="Ingest Job", description=""))
    path = tmp_path / "plan.dxf"
    path.write_text("0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n", encoding="utf-8")
    result = IngestionService(db_session).import_file(project.id, path)
    assert result.error is None
    assert result.document is not None
    assert result.document.metadata.get("analyze_queued") is True
    job_id = result.document.metadata.get("background_job_id")
    assert job_id
    api = api_from_session(db_session)
    from uuid import UUID

    job = api.jobs.get(UUID(str(job_id)))
    assert job is not None
    assert job.kind == BackgroundJobKind.DOCUMENT_ANALYZE


def test_slides_and_visual_api_load_presentation(db_session: Session) -> None:
    from archium.domain.enums import SlideStatus, SlideType
    from archium.domain.presentation import Presentation
    from archium.domain.slide import SlideSpec
    from archium.infrastructure.database.repositories import PresentationRepository

    project = ProjectRepository(db_session).create(Project(name="Visual API", description=""))
    presentations = PresentationRepository(db_session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="视觉门面")
    )
    slide = presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="首页",
            message="核心信息",
            slide_type=SlideType.CONTENT,
            status=SlideStatus.PLANNED,
        )
    )
    api = api_from_session(db_session)
    assert api.slides.get(slide.id) is not None
    listed = api.slides.list_for_presentation(presentation.id)
    assert len(listed) == 1
    loaded = api.visual.load_presentation_visual(presentation.id)
    assert loaded.presentation_id == presentation.id
    assert len(loaded.slides) == 1
    assert loaded.slides[0].slide.id == slide.id
    assert loaded.slides[0].visual_intent is None
    assert loaded.slides[0].layout_plan is None


def test_mission_api_get(db_session: Session) -> None:
    from archium.domain.project_mission import ProjectMission
    from archium.infrastructure.database.mission_repositories import MissionRepository

    project = ProjectRepository(db_session).create(Project(name="Mission API", description=""))
    mission = MissionRepository(db_session).save_mission(
        ProjectMission(
            project_id=project.id,
            title="任务",
            task_statement="澄清任务边界",
        )
    )
    api = api_from_session(db_session)
    got = api.mission.get(mission.id)
    assert got is not None
    assert got.id == mission.id
    assert got.title == "任务"
    assert api.mission.list_deliverable_plans(mission.id) == []
    assert api.mission.list_workstreams(mission.id) == []
    assert api.context.list_facts(project.id) == []


def test_planning_api_resolve_run_and_session(db_session: Session) -> None:
    from archium.domain.enums import WorkflowStatus
    from archium.domain.planning_session import PlanningSession
    from archium.domain.workflow import WorkflowRun
    from archium.infrastructure.database.repositories import (
        PlanningSessionRepository,
        WorkflowRunRepository,
    )

    project = ProjectRepository(db_session).create(Project(name="Planning API", description=""))
    run = WorkflowRunRepository(db_session).create(
        WorkflowRun(
            project_id=project.id,
            status=WorkflowStatus.RUNNING,
            state={"workflow_kind": "planning"},
        )
    )
    session_row = PlanningSessionRepository(db_session).create(
        PlanningSession(
            project_id=project.id,
            workflow_run_id=run.id,
            user_task_description="策划会话",
        )
    )
    api = api_from_session(db_session)
    assert api.planning.get_run(run.id) is not None
    resolved_session = api.planning.resolve_session(project_id=project.id)
    assert resolved_session is not None
    assert resolved_session.id == session_row.id
    resolved_run, linked = api.planning.resolve_run(project_id=project.id)
    assert resolved_run is not None
    assert resolved_run.id == run.id
    assert linked is not None
    assert linked.id == session_row.id
