"""Integration tests for v0.2 stabilization sprint guarantees."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.config.settings import Settings, reset_settings
from archium.domain.enums import ProjectType, WorkflowStatus
from archium.domain.project import Project
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.database.session import (
    create_engine_from_settings,
    get_session,
    reset_engine_cache,
)
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mock_llm import pipeline_mock_selector


@pytest.fixture
def request_payload() -> PresentationRequest:
    return PresentationRequest(
        title="Stabilization Test",
        audience="QA",
        purpose="Verify stabilization guarantees",
        duration_minutes=10,
        target_slide_count=2,
        core_message="Stability over features",
    )


def test_workflow_completes_with_retrieval_disabled(
    db_session: Session,
    request_payload: PresentationRequest,
) -> None:
    """Main pipeline must run when vector retrieval is turned off."""
    settings = Settings(
        _env_file=None,
        database_path=Path("unused.db"),
        retrieval_enabled=False,
        embedding_provider="openai_compatible",
        embedding_model=None,
        llm_api_key=None,
    )
    project = ProjectRepository(db_session).create(
        Project(name="No Retrieval Project", project_type=ProjectType.HEALTHCARE)
    )
    mock_llm = MockLLMProvider(selector=pipeline_mock_selector)
    service = PresentationWorkflowService(db_session, mock_llm, settings=settings)

    result = service.run(project.id, request_payload, export_marp=False)

    assert result.succeeded
    assert result.workflow_run.status == WorkflowStatus.COMPLETED
    assert len(result.slides) == 4


def test_database_path_consistent_across_working_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request_payload: PresentationRequest,
) -> None:
    """SQLite URL must resolve to the project root regardless of process cwd."""
    reset_settings()
    reset_engine_cache()

    project_root = Path(__file__).resolve().parents[2]
    db_file = tmp_path / "isolated" / "archium.db"
    db_file.parent.mkdir(parents=True)

    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_file.as_posix()}",
    )
    assert settings.resolved_database_url == f"sqlite:///{db_file.resolve().as_posix()}"

    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)

    nested_cwd = tmp_path / "nested" / "cwd"
    nested_cwd.mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)

    reset_settings()
    reset_engine_cache()
    cwd_settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_file.as_posix()}",
    )
    assert cwd_settings.resolved_database_url == settings.resolved_database_url

    mock_llm = MockLLMProvider(selector=pipeline_mock_selector)
    with get_session(engine) as session:
        project = ProjectRepository(session).create(
            Project(name="CWD Test Project", project_type=ProjectType.HEALTHCARE)
        )
        service = PresentationWorkflowService(session, mock_llm, settings=cwd_settings)
        result = service.run(project.id, request_payload, export_marp=False)
        assert result.succeeded

    assert db_file.exists()
    engine.dispose()


def test_relative_database_url_resolves_to_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relative DATABASE_URL must normalize against the repository root, not cwd."""
    reset_settings()
    monkeypatch.chdir(tmp_path)

    project_root = Path(__file__).resolve().parents[2]
    settings = Settings(
        _env_file=None,
        database_url="sqlite:///data/database/custom.db",
    )
    expected = (project_root / "data/database/custom.db").resolve()
    assert settings.resolved_database_url == f"sqlite:///{expected.as_posix()}"


def test_app_imports_without_api_key() -> None:
    """Streamlit entry and UI modules must import without configured API keys."""
    reset_settings()
    reset_engine_cache()

    import app  # noqa: F401
    import archium.ui.bootstrap  # noqa: F401
    import archium.ui.pages.workspace  # noqa: F401

    settings = Settings(_env_file=None, llm_api_key=None, embedding_api_key=None)
    assert settings.llm_configured is False
    assert settings.embedding_configured is False
