"""Integration tests for PresentationManuscript workflow wiring."""

from __future__ import annotations

import pytest
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.application.review_service import PresentationReviewService
from archium.domain.document import DocumentChunk
from archium.domain.enums import ProjectType, WorkflowStatus, WorkflowStep
from archium.domain.fact import ProjectFact
from archium.domain.presentation_manuscript import ManuscriptStatus
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    ProjectRepository,
)
from archium.infrastructure.llm import MockLLMProvider
from archium.workflow.serialization import restore_domain_artifacts
from sqlalchemy.orm import Session

from tests.fixtures.mock_llm import pipeline_mock_selector


@pytest.fixture
def project_with_context(db_session: Session) -> Project:
    project = ProjectRepository(db_session).create(
        Project(name="某医院老院区更新", project_type=ProjectType.HEALTHCARE)
    )
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
def workflow_service(db_session: Session, test_settings: object) -> PresentationWorkflowService:
    mock_llm = MockLLMProvider(selector=pipeline_mock_selector)
    return PresentationWorkflowService(db_session, mock_llm, settings=test_settings)  # type: ignore[arg-type]


@pytest.fixture
def manuscript_request() -> PresentationRequest:
    return PresentationRequest(
        title="老院区更新概念汇报",
        audience="医院管理层",
        purpose="确认总体改造方向",
        duration_minutes=20,
        target_slide_count=4,
        core_message="通过交通重组改善体验",
        required_sections=["现状分析", "改造策略"],
        use_manuscript_pipeline=True,
    )


def test_manuscript_pipeline_completes_without_review_gate(
    workflow_service: PresentationWorkflowService,
    project_with_context: Project,
    manuscript_request: PresentationRequest,
) -> None:
    result = workflow_service.run(
        project_with_context.id,
        manuscript_request,
        require_manuscript_review=False,
        require_outline_review=False,
        export_marp=False,
    )

    assert result.succeeded
    restored = restore_domain_artifacts(result.workflow_run.state)
    manuscript = restored.get("manuscript")
    assert manuscript is not None
    assert manuscript.status == ManuscriptStatus.READY
    assert len(result.slides) == 4
    assert result.workflow_run.status == WorkflowStatus.COMPLETED


def test_workflow_pauses_for_manuscript_review(
    workflow_service: PresentationWorkflowService,
    project_with_context: Project,
    manuscript_request: PresentationRequest,
    db_session: Session,
) -> None:
    first = workflow_service.run(
        project_with_context.id,
        manuscript_request,
        require_manuscript_review=True,
        require_brief_review=False,
        require_storyline_review=False,
        require_outline_review=False,
        export_marp=False,
    )

    assert first.awaiting_review
    assert first.workflow_run.status == WorkflowStatus.AWAITING_REVIEW
    assert first.workflow_run.state["review_gate"] == "manuscript"
    assert first.workflow_run.state["current_step"] == WorkflowStep.REVIEW_MANUSCRIPT.value

    restored = restore_domain_artifacts(first.workflow_run.state)
    manuscript = restored.get("manuscript")
    assert manuscript is not None
    assert manuscript.status == ManuscriptStatus.DRAFT
    assert first.brief is None

    review_service = PresentationReviewService(db_session)
    review_service.approve_manuscript(manuscript.id)
    db_session.commit()

    second = workflow_service.continue_after_review(first.workflow_run.id)
    assert second.brief is not None
    assert len(second.slides) == 4
    assert second.workflow_run.status == WorkflowStatus.COMPLETED
