"""Integration tests for PresentationService atomic step APIs.

Full pipeline execution uses :class:`PresentationWorkflowService` — see
``tests/integration/test_presentation_workflow.py``.
"""

from __future__ import annotations

import pytest
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_service import PresentationService
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.domain.document import DocumentChunk
from archium.domain.enums import ProjectType
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    PresentationRepository,
    ProjectRepository,
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
def presentation_service(
    db_session: Session,
    test_settings: object,
    mock_llm: MockLLMProvider,
) -> PresentationService:
    return PresentationService(db_session, mock_llm, settings=test_settings)  # type: ignore[arg-type]


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


def test_presentation_service_has_no_run_pipeline() -> None:
    assert not hasattr(PresentationService, "run_pipeline")


def test_regenerate_slide_plan_replaces_slides(
    db_session: Session,
    test_settings: object,
    mock_llm: MockLLMProvider,
    project_with_context: Project,
    request_payload: PresentationRequest,
    presentation_service: PresentationService,
) -> None:
    workflow = PresentationWorkflowService(db_session, mock_llm, settings=test_settings)  # type: ignore[arg-type]
    try:
        first = workflow.run(project_with_context.id, request_payload)
    finally:
        workflow.close()
    assert first.brief and first.storyline

    second_slides = presentation_service.generate_slide_plan(
        project_with_context.id,
        first.brief,
        first.storyline,
    )
    pres_repo = PresentationRepository(db_session)
    stored = pres_repo.list_slides(first.presentation.id)
    assert len(stored) == len(second_slides) == 4


def test_pipeline_step_methods(
    presentation_service: PresentationService,
    project_with_context: Project,
    request_payload: PresentationRequest,
) -> None:
    presentation = presentation_service.create_presentation(
        project_with_context.id,
        request_payload,
    )
    brief = presentation_service.generate_brief(
        project_with_context.id,
        presentation.id,
        request_payload,
    )
    storyline = presentation_service.generate_storyline(project_with_context.id, brief)
    slides = presentation_service.generate_slide_plan(
        project_with_context.id,
        brief,
        storyline,
    )

    assert brief.core_message
    assert len(storyline.chapters) == 2
    assert len(slides) == 4
