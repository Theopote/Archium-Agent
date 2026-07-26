"""Unit tests for ProjectEvent log + JobProgress + LLMTrace persistence."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from archium.application.job_progress_service import JobProgressService
from archium.application.project_event_service import ProjectEventService
from archium.domain.enums import WorkflowStatus
from archium.domain.intent.intent_evolution import IntentEvolution, IntentEvolutionKind
from archium.domain.project import Project
from archium.domain.project_event import ProjectEventType
from archium.domain.workflow import WorkflowRun
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.repositories import (
    ProjectRepository,
    WorkflowRunRepository,
)
from archium.infrastructure.llm.trace import (
    DatabaseLLMTraceRecorder,
    InMemoryLLMTraceRecorder,
    LLMTrace,
    set_llm_trace_recorder,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


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
        session.commit()
    finally:
        session.close()
        engine.dispose()
        set_llm_trace_recorder(None)


def test_project_create_emits_and_intent_projects(db_session: Session) -> None:
    project = Project(name="秦岭文化中心", description="概念")
    evo = IntentEvolution().append(
        IntentEvolutionKind.SEED,
        "初始想法：秦岭文化中心",
        new_summary="秦岭文化中心",
    )
    evo = evo.append(
        IntentEvolutionKind.DIRECTION_SELECTED,
        "选定生态共生",
        previous_summary="现代主义",
        new_summary="生态共生",
        reason="研究发现当地聚落特点",
    )
    project.intent_evolution = evo
    saved = ProjectRepository(db_session).create(project)
    db_session.flush()

    events = ProjectEventService(db_session).list_for_project(saved.id, limit=20)
    types = {item.event_type for item in events}
    assert ProjectEventType.PROJECT_CREATED in types
    assert ProjectEventType.CONCEPT_SELECTED in types
    assert ProjectEventType.CONTEXT_UPDATED in types

    inserted = ProjectEventService(db_session).sync_from_intent_evolution(
        saved.id, saved.intent_evolution
    )
    assert inserted == 0


def test_process_timeline_projects_to_events(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="进程测试"))
    run = WorkflowRun(
        project_id=project.id,
        status=WorkflowStatus.RUNNING,
        state={
            "workflow_kind": "orchestration",
            "process_timeline": [
                {
                    "at": datetime.now(UTC).isoformat(),
                    "kind": "stage",
                    "stage": "research",
                    "status": "done",
                    "label": "研究完成",
                    "summary": "地域文化检索",
                }
            ],
        },
    )
    created = WorkflowRunRepository(db_session).create(run)
    WorkflowRunRepository(db_session).update(created)
    events = ProjectEventService(db_session).list_for_project(project.id, limit=20)
    assert any(item.event_type == ProjectEventType.PROCESS_CHECKPOINT for item in events)


def test_job_progress_unifies_workflow(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="任务测试"))
    WorkflowRunRepository(db_session).create(
        WorkflowRun(
            project_id=project.id,
            status=WorkflowStatus.RUNNING,
            state={"workflow_kind": "planning", "current_step": "mission"},
        )
    )
    rows = JobProgressService(db_session).list_for_project(project.id, limit=10)
    assert rows
    assert rows[0].kind.value == "workflow"
    assert rows[0].progress_pct is not None
    assert "规划" in rows[0].label


def test_database_llm_trace_recorder(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(
        "archium.config.settings.get_settings",
        lambda: type("S", (), {"llm_trace_persist_enabled": True})(),
    )
    project = ProjectRepository(db_session).create(Project(name="Trace项目"))
    set_llm_trace_recorder(InMemoryLLMTraceRecorder())
    recorder = DatabaseLLMTraceRecorder()
    recorder.record(
        LLMTrace(
            request_id="abc123",
            provider="openai_compatible",
            model="test-model",
            capability="mission",
            project_id=str(project.id),
            total_tokens=42,
            latency_ms=12.5,
            success=True,
        )
    )
    from archium.infrastructure.database.repositories import LLMTraceRepository

    traces = LLMTraceRepository(db_session).list_for_project(project.id, limit=10)
    assert traces
    assert traces[0].total_tokens == 42
    assert traces[0].request_id == "abc123"
