"""Unit tests for architecture slide semantic QA."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.automated_review_service import AutomatedReviewService
from archium.application.chunk_models import ProjectContextBundle
from archium.application.slide_semantic_qa_service import run_slide_semantic_qa
from archium.domain.asset import Asset
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import (
    DocumentPurpose,
    ProjectType,
    ReviewLayer,
    VisualType,
)
from archium.domain.presentation import Presentation, PresentationBrief
from archium.domain.project import Project
from archium.domain.renovation_issue import RenovationIssueMap
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.slide_semantic_qa import SlideSemanticCheckCode
from archium.infrastructure.database.repositories import (
    AssetRepository,
    DocumentRepository,
    PresentationRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


def _slide(
    presentation_id: object,
    *,
    order: int = 1,
    message: str = "本项目交通组织优化后通行效率提升。",
    title: str = "交通优化",
    visual_requirements: list[VisualRequirement] | None = None,
) -> SlideSpec:
    return SlideSpec(
        presentation_id=presentation_id,  # type: ignore[arg-type]
        chapter_id="ch1",
        order=order,
        title=title,
        message=message,
        visual_requirements=visual_requirements or [],
    )


def test_reference_asset_used_as_project_asset() -> None:
    presentation_id = uuid4()
    project_id = uuid4()
    asset_id = uuid4()
    document_id = uuid4()
    asset = Asset(
        id=asset_id,
        project_id=project_id,
        document_id=document_id,
        filename="ref-case.png",
        path="/tmp/ref-case.png",
        width=1400,
        height=900,
    )
    documents = {
        document_id: SourceDocument(
            id=document_id,
            project_id=project_id,
            filename="ref.pptx",
            original_path="/tmp/ref.pptx",
            stored_path="/tmp/ref.pptx",
            file_type="pptx",
            file_hash="a" * 64,
            size_bytes=100,
            metadata={"purpose": DocumentPurpose.REFERENCE_CASE.value},
        )
    }
    slide = _slide(
        presentation_id,
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="现场照片",
                preferred_asset_ids=[asset_id],
            )
        ],
    )

    report = run_slide_semantic_qa(
        presentation_id,
        [slide],
        project_id=project_id,
        assets_by_id={asset_id: asset},
        documents_by_id=documents,
    )

    codes = {finding.check_code for finding in report.findings}
    assert SlideSemanticCheckCode.REFERENCE_ASSET_USED_AS_PROJECT_ASSET in codes


def test_project_asset_without_source_when_chunks_exist() -> None:
    presentation_id = uuid4()
    project_id = uuid4()
    asset_id = uuid4()
    asset = Asset(
        id=asset_id,
        project_id=project_id,
        filename="project-plan.png",
        path="/tmp/project-plan.png",
        width=1400,
        height=900,
    )
    slide = _slide(
        presentation_id,
        visual_requirements=[
            VisualRequirement(
                type=VisualType.FLOOR_PLAN,
                description="一层平面图",
                preferred_asset_ids=[asset_id],
            )
        ],
    )

    report = run_slide_semantic_qa(
        presentation_id,
        [slide],
        project_id=project_id,
        assets_by_id={asset_id: asset},
        has_project_sources=True,
    )

    codes = {finding.check_code for finding in report.findings}
    assert SlideSemanticCheckCode.PROJECT_ASSET_WITHOUT_SOURCE in codes


def test_renovation_issue_without_evidence() -> None:
    presentation_id = uuid4()
    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,
        title="改造汇报",
        audience="甲方",
        purpose="老旧建筑改造",
        core_message="提升品质",
    )
    slide = _slide(
        presentation_id,
        message="屋面渗漏问题严重，需尽快整治。",
        title="现状问题",
    )
    issue_map = RenovationIssueMap(
        project_id=brief.project_id,
        building_summary="老旧教学楼",
    )

    report = run_slide_semantic_qa(
        presentation_id,
        [slide],
        brief=brief,
        renovation_issue_map=issue_map,
    )

    codes = {finding.check_code for finding in report.findings}
    assert SlideSemanticCheckCode.ISSUE_WITHOUT_EVIDENCE in codes


def test_before_after_mismatch_flags_single_visual() -> None:
    presentation_id = uuid4()
    asset_id = uuid4()
    slide = _slide(
        presentation_id,
        title="改造前后对比",
        message="改造前后公共空间品质显著提升。",
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="改造后实景",
                preferred_asset_ids=[asset_id],
            )
        ],
    )

    report = run_slide_semantic_qa(
        presentation_id,
        [slide],
        assets_by_id={
            asset_id: Asset(
                id=asset_id,
                project_id=uuid4(),
                filename="after.jpg",
                path="/tmp/after.jpg",
                width=1200,
                height=800,
            )
        },
    )

    codes = {finding.check_code for finding in report.findings}
    assert SlideSemanticCheckCode.BEFORE_AFTER_MISMATCH in codes


def test_external_fact_without_citation() -> None:
    presentation_id = uuid4()
    slide = _slide(
        presentation_id,
        message="行业研究显示公共空间使用率持续上升。",
    )

    report = run_slide_semantic_qa(presentation_id, [slide])

    codes = {finding.check_code for finding in report.findings}
    assert SlideSemanticCheckCode.EXTERNAL_FACT_WITHOUT_CITATION in codes


@pytest.fixture
def semantic_presentation(db_session: Session) -> tuple[object, object]:
    project = ProjectRepository(db_session).create(
        Project(name="Semantic QA Project", project_type=ProjectType.URBAN_RENEWAL)
    )
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="Semantic QA Test")
    )
    return project.id, presentation.id


def test_slide_semantic_review_persists_issues(
    db_session: Session,
    semantic_presentation: tuple[object, object],
) -> None:
    project_id, presentation_id = semantic_presentation
    doc_repo = DocumentRepository(db_session)
    document = doc_repo.create_document(
        SourceDocument(
            project_id=project_id,  # type: ignore[arg-type]
            filename="ref-style.pptx",
            original_path="/tmp/ref-style.pptx",
            stored_path="/tmp/ref-style.pptx",
            file_type="pptx",
            file_hash="b" * 64,
            size_bytes=100,
            metadata={"purpose": DocumentPurpose.REFERENCE_STYLE.value},
        )
    )
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project_id,  # type: ignore[arg-type]
            document_id=document.id,
            filename="ref-style.png",
            path="/tmp/ref-style.png",
            width=1400,
            height=900,
        )
    )
    slide = _slide(
        presentation_id,
        visual_requirements=[
            VisualRequirement(
                type=VisualType.RENDERING,
                description="效果图",
                preferred_asset_ids=[asset.id],
            )
        ],
    )
    chunk = DocumentChunk(
        document_id=document.id,
        project_id=project_id,  # type: ignore[arg-type]
        chunk_index=0,
        content="项目资料",
    )
    bundle = ProjectContextBundle(text="ctx", chunks=[chunk])

    issues = AutomatedReviewService(db_session).run_slide_semantic_review(
        presentation_id,  # type: ignore[arg-type]
        [slide],
        project_id=project_id,  # type: ignore[arg-type]
        context_bundle=bundle,
    )

    assert issues
    assert issues[0].reviewer_layer == ReviewLayer.SEMANTIC
    assert issues[0].rule_code == ReviewRuleCode.SEMANTIC_REFERENCE_ASSET_USED_AS_PROJECT_ASSET
