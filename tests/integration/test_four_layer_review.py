"""Integration tests for four-layer presentation review in workflow."""

from __future__ import annotations

from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.domain.document import DocumentChunk
from archium.domain.enums import ProjectType, ReviewLayer, WorkflowStatus
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    PresentationRepository,
    ProjectRepository,
    ReviewRepository,
)
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mock_llm import pipeline_mock_selector


def test_workflow_persists_multi_layer_review_issues(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="Review Layers Project", project_type=ProjectType.HEALTHCARE)
    )
    doc_repo = DocumentRepository(db_session)
    from archium.domain.document import SourceDocument
    from archium.domain.enums import DocumentType, ProcessingStatus

    document = doc_repo.create_document(
        SourceDocument(
            project_id=project.id,
            filename="任务书.pdf",
            original_path="/tmp/任务书.pdf",
            stored_path="/tmp/任务书.pdf",
            file_type=DocumentType.PDF,
            file_hash="d" * 64,
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
    FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="site_area",
            label="用地面积",
            value="12.5 公顷",
        )
    )

    payload = PresentationRequest(
        title="老院区更新概念汇报",
        audience="医院管理层",
        purpose="确认总体改造方向",
        duration_minutes=20,
        target_slide_count=4,
        core_message="通过交通重组改善体验",
        required_sections=["院区现状", "改造策略"],
    )
    mock_llm = MockLLMProvider(selector=pipeline_mock_selector)
    service = PresentationWorkflowService(db_session, mock_llm, settings=test_settings)  # type: ignore[arg-type]

    result = service.run(
        project.id,
        payload,
        require_brief_review=False,
        require_storyline_review=False,
        require_slides_review=False,
        export_marp=False,
    )

    assert result.succeeded
    assert result.workflow_run.status == WorkflowStatus.COMPLETED

    issues = ReviewRepository(db_session).list_by_presentation(result.presentation.id)
    layers = {issue.reviewer_layer for issue in issues}
    assert ReviewLayer.EVIDENCE in layers
    assert ReviewLayer.ARCHITECTURAL in layers
    assert ReviewLayer.LAYOUT in layers
    assert len(layers) >= 3

    titles = {issue.title for issue in issues}
    assert any("缺少引用来源" in title or "数值结论缺少依据" in title for title in titles)
    assert any("交通流线图缺少颜色图例提示" in title for title in titles)
    assert any("缺少匹配素材" in title for title in titles)

    presentations = PresentationRepository(db_session).list_by_project(project.id)
    assert presentations
