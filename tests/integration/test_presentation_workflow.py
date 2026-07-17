"""Integration tests for LangGraph presentation workflow."""

from __future__ import annotations

import json

import pytest
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.domain.document import DocumentChunk
from archium.domain.enums import (
    PresentationStatus,
    ProjectType,
    WorkflowStatus,
    WorkflowStep,
)
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    PresentationRepository,
    ProjectRepository,
    WorkflowRunRepository,
)
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mock_llm import pipeline_mock_selector


@pytest.fixture
def project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(
        Project(name="某医院老院区更新", project_type=ProjectType.HEALTHCARE)
    )


@pytest.fixture
def project_with_context(db_session: Session, project: Project) -> Project:
    doc_repo = DocumentRepository(db_session)
    fact_repo = FactRepository(db_session)
    from archium.domain.document import SourceDocument
    from archium.domain.enums import DocumentType, ProcessingStatus

    document = doc_repo.create_document(
        SourceDocument(
            project_id=project.id,
            filename="任务书.pdf",
            original_path="/tmp/任务书.pdf",
            stored_path="/tmp/任务书.pdf",
            file_type=DocumentType.PDF,
            file_hash="a" * 64,
            size_bytes=1024,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    doc_repo.create_chunk(
        DocumentChunk(
            document_id=document.id,
            project_id=project.id,
            chunk_index=0,
            content="老院区交通组织混乱，人车混行严重。",
            page_number=1,
            section_title="现状",
        )
    )
    fact_repo.create(
        ProjectFact(
            project_id=project.id,
            key="site_area",
            label="用地面积",
            value="12.5 公顷",
        )
    )
    return project


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    return MockLLMProvider(selector=pipeline_mock_selector)


@pytest.fixture
def workflow_service(
    db_session: Session,
    test_settings: object,
    mock_llm: MockLLMProvider,
) -> PresentationWorkflowService:
    return PresentationWorkflowService(db_session, mock_llm, settings=test_settings)  # type: ignore[arg-type]


@pytest.fixture
def request_payload() -> PresentationRequest:
    return PresentationRequest(
        title="老院区更新概念汇报",
        audience="医院管理层",
        purpose="确认总体改造方向",
        duration_minutes=20,
        target_slide_count=4,
        core_message="通过交通重组改善体验",
        required_sections=["现状分析", "改造策略"],
    )


def test_workflow_run_persists_artifacts(
    workflow_service: PresentationWorkflowService,
    project_with_context: Project,
    request_payload: PresentationRequest,
    db_session: Session,
    mock_llm: MockLLMProvider,
) -> None:
    result = workflow_service.run(project_with_context.id, request_payload)

    assert result.succeeded
    assert result.workflow_run.status == WorkflowStatus.COMPLETED
    assert result.workflow_run.state["current_step"] == WorkflowStep.FINALIZE.value
    assert result.brief is not None
    assert result.storyline is not None
    assert len(result.slides) == 4
    assert result.presentation.status == PresentationStatus.REVIEW

    pres_repo = PresentationRepository(db_session)
    assert len(pres_repo.list_briefs(result.presentation.id)) == 1
    assert len(pres_repo.list_storylines(result.presentation.id)) == 1
    assert len(pres_repo.list_slides(result.presentation.id)) == 4
    assert len(mock_llm.calls) == 3

    workflow_runs = WorkflowRunRepository(db_session).list_by_presentation(result.presentation.id)
    assert len(workflow_runs) == 1
    assert workflow_runs[0].output_files


def test_workflow_run_exports_json(
    workflow_service: PresentationWorkflowService,
    project_with_context: Project,
    request_payload: PresentationRequest,
) -> None:
    result = workflow_service.run(project_with_context.id, request_payload)

    assert result.json_path is not None
    assert result.json_path.exists()
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert payload["brief"]["title"] == "老院区更新概念汇报"
    assert len(payload["slides"]) == 4


def test_workflow_run_exports_marp(
    workflow_service: PresentationWorkflowService,
    project_with_context: Project,
    request_payload: PresentationRequest,
) -> None:
    result = workflow_service.run(
        project_with_context.id,
        request_payload,
        export_marp=True,
    )

    assert result.succeeded
    assert result.marp_md_path is not None
    assert result.marp_md_path.exists()
    assert result.workflow_run.state["current_step"] == WorkflowStep.FINALIZE.value
    assert any(path.endswith("presentation.md") for path in result.workflow_run.output_files)


def test_workflow_resume_completed_run_is_idempotent(
    workflow_service: PresentationWorkflowService,
    project_with_context: Project,
    request_payload: PresentationRequest,
    mock_llm: MockLLMProvider,
) -> None:
    first = workflow_service.run(project_with_context.id, request_payload)
    call_count = len(mock_llm.calls)

    second = workflow_service.resume(first.workflow_run.id)

    assert second.succeeded
    assert second.workflow_run.status == WorkflowStatus.COMPLETED
    assert len(mock_llm.calls) == call_count
