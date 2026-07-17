"""Unit tests for workflow checkpointer lifecycle."""

from __future__ import annotations

from pathlib import Path

from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.config.settings import Settings
from archium.domain.enums import ProjectType, WorkflowStatus
from archium.domain.project import Project
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm import MockLLMProvider
from archium.workflow.checkpointer import WorkflowCheckpointerManager
from sqlalchemy.orm import Session

from tests.fixtures.mock_llm import pipeline_mock_selector


def test_checkpointer_manager_closes_and_allows_db_deletion(tmp_path: Path) -> None:
    db_path = tmp_path / "checkpoints" / "workflow.db"
    with WorkflowCheckpointerManager(db_path) as manager:
        _ = manager.saver
        assert db_path.exists()

    db_path.unlink()
    assert not db_path.exists()


def test_workflow_service_closes_checkpointer_after_run(
    db_session: Session,
    test_settings: Settings,
) -> None:
    checkpoint_path = test_settings.workflow_checkpoint_path
    manager = WorkflowCheckpointerManager(checkpoint_path)
    project = ProjectRepository(db_session).create(
        Project(name="Checkpointer Lifecycle", project_type=ProjectType.HEALTHCARE)
    )
    mock_llm = MockLLMProvider(selector=pipeline_mock_selector)
    service = PresentationWorkflowService(
        db_session,
        mock_llm,
        settings=test_settings,
        checkpointer_manager=manager,
    )
    payload = PresentationRequest(
        title="Lifecycle Test",
        audience="QA",
        purpose="Verify checkpoint cleanup",
        duration_minutes=10,
        target_slide_count=2,
        core_message="Close SQLite after workflow",
    )

    try:
        result = service.run(project.id, payload, export_marp=False)
        assert result.workflow_run.status == WorkflowStatus.COMPLETED
        assert checkpoint_path.exists()
    finally:
        service.close()

    checkpoint_path.unlink()
    assert not checkpoint_path.exists()
