"""Integration tests for critical review export blocking."""

from __future__ import annotations

import pytest
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.domain.document import DocumentChunk
from archium.domain.enums import ProjectType, WorkflowStatus
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.exceptions import WorkflowError
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
            file_hash="b" * 64,
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


@pytest.fixture
def blocking_settings(test_settings: object) -> object:
    from archium.config.settings import Settings

    assert isinstance(test_settings, Settings)
    return test_settings.model_copy(update={"block_export_on_critical_review": True})


def test_workflow_blocks_export_on_critical_review(
    project_with_context: Project,
    request_payload: PresentationRequest,
    db_session: Session,
    blocking_settings: object,
) -> None:
    mock_llm = MockLLMProvider(selector=pipeline_mock_selector)
    service = PresentationWorkflowService(db_session, mock_llm, settings=blocking_settings)  # type: ignore[arg-type]

    with pytest.raises(WorkflowError, match="必要章节未覆盖|现状分析"):
        service.run(
            project_with_context.id,
            request_payload,
            require_brief_review=False,
            require_storyline_review=False,
            require_outline_review=False,
            require_slides_review=False,
            export_marp=False,
        )

    presentations = PresentationRepository(db_session).list_by_project(project_with_context.id)
    assert presentations
    runs = WorkflowRunRepository(db_session).list_by_presentation(presentations[0].id)
    assert runs
    assert runs[0].status == WorkflowStatus.FAILED
    assert runs[0].state.get("json_path") is None
    assert any("必要章节未覆盖" in error or "现状分析" in error for error in runs[0].errors)
