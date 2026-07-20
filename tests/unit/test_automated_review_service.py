"""Unit tests for automated four-layer presentation review."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.automated_review_service import AutomatedReviewService
from archium.application.chunk_models import ProjectContextBundle
from archium.domain.document import DocumentChunk
from archium.domain.enums import (
    PresentationType,
    ProjectType,
    ReviewCategory,
    ReviewLayer,
    ReviewSeverity,
    VisualType,
)
from archium.domain.presentation import Presentation, PresentationBrief
from archium.domain.project import Project
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
    ReviewRepository,
)
from sqlalchemy.orm import Session


@pytest.fixture
def presentation_id(db_session: Session) -> object:
    project = ProjectRepository(db_session).create(
        Project(name="Review Project", project_type=ProjectType.HEALTHCARE)
    )
    return PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="Review Test")
    ).id


def test_evidence_review_flags_missing_citation(
    db_session: Session,
    presentation_id: object,
) -> None:
    slide = SlideSpec(
        presentation_id=presentation_id,  # type: ignore[arg-type]
        chapter_id="ch1",
        order=1,
        title="核心问题",
        message="人车混行导致效率低",
    )
    chunk = DocumentChunk(
        document_id=uuid4(),
        project_id=uuid4(),
        chunk_index=0,
        content="交通组织混乱",
    )
    bundle = ProjectContextBundle(text="ctx", chunks=[chunk])

    issues = AutomatedReviewService(db_session).run_evidence_review(
        presentation_id,  # type: ignore[arg-type]
        [slide],
        context_bundle=bundle,
    )

    assert len(issues) == 1
    assert issues[0].category == ReviewCategory.CITATION
    assert issues[0].reviewer_layer == ReviewLayer.EVIDENCE
    assert issues[0].rule_code == ReviewRuleCode.EVIDENCE_MISSING_CITATION
    assert ReviewRepository(db_session).list_by_presentation(presentation_id)  # type: ignore[arg-type]


def test_evidence_review_flags_numeric_claim_without_source(
    db_session: Session,
    presentation_id: object,
) -> None:
    slide = SlideSpec(
        presentation_id=presentation_id,  # type: ignore[arg-type]
        chapter_id="ch1",
        order=0,
        title="规模",
        message="总建筑面积 12000 平方米",
    )

    issues = AutomatedReviewService(db_session).run_evidence_review(
        presentation_id,  # type: ignore[arg-type]
        [slide],
    )

    assert any(issue.rule_code == ReviewRuleCode.EVIDENCE_NUMERIC_CLAIM_UNCITED for issue in issues)
    assert all(issue.reviewer_layer == ReviewLayer.EVIDENCE for issue in issues)


def test_content_review_flags_duplicate_titles(
    db_session: Session,
    presentation_id: object,
) -> None:
    slides = [
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="ch1",
            order=i,
            title="改造策略",
            message=f"结论 {i}",
        )
        for i in range(2)
    ]

    issues = AutomatedReviewService(db_session).run_content_review(
        presentation_id,  # type: ignore[arg-type]
        slides,
    )

    assert any(issue.rule_code == ReviewRuleCode.CONTENT_DUPLICATE_TITLE for issue in issues)
    assert all(issue.reviewer_layer == ReviewLayer.CONTENT for issue in issues)


def test_layout_review_flags_missing_visual_asset(
    db_session: Session,
    presentation_id: object,
) -> None:
    slide = SlideSpec(
        presentation_id=presentation_id,  # type: ignore[arg-type]
        chapter_id="ch1",
        order=0,
        title="改造策略",
        message="通过交通重组释放空间",
        visual_requirements=[
            VisualRequirement(type=VisualType.DIAGRAM, description="交通重组示意", required=True)
        ],
    )

    issues = AutomatedReviewService(db_session).run_layout_review(
        presentation_id,  # type: ignore[arg-type]
        [slide],
    )

    layout_issues = [
        issue for issue in issues if issue.rule_code == ReviewRuleCode.LAYOUT_MISSING_ASSET
    ]
    assert len(layout_issues) == 1
    assert layout_issues[0].category == ReviewCategory.VISUAL
    assert layout_issues[0].reviewer_layer == ReviewLayer.LAYOUT


def test_critical_export_block_messages() -> None:
    from archium.application.automated_review_service import critical_export_block_messages

    presentation_id = uuid4()
    open_critical = ReviewIssue(
        presentation_id=presentation_id,
        category=ReviewCategory.CONTENT,
        severity=ReviewSeverity.CRITICAL,
        rule_code=ReviewRuleCode.CONTENT_MISSING_MESSAGE,
        title="缺少核心信息",
        description="第 2 页缺少核心结论。",
    )
    resolved = ReviewIssue(
        presentation_id=presentation_id,
        category=ReviewCategory.COVERAGE,
        severity=ReviewSeverity.CRITICAL,
        rule_code=ReviewRuleCode.ARCH_REQUIRED_SECTION_MISSING,
        title="必要章节未覆盖",
        description="Brief 要求包含「改造策略」。",
    )
    resolved.resolve()

    assert critical_export_block_messages([open_critical, resolved], block_enabled=False) == []
    messages = critical_export_block_messages([open_critical, resolved], block_enabled=True)
    assert len(messages) == 1
    assert "缺少核心信息" in messages[0]


def test_architectural_review_flags_slide_count_drift(
    db_session: Session,
    presentation_id: object,
) -> None:
    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,  # type: ignore[arg-type]
        title="Brief",
        presentation_type=PresentationType.CLIENT_REVIEW,
        audience="管理层",
        purpose="决策",
        duration_minutes=20,
        target_slide_count=10,
        core_message="核心",
    )
    slides = [
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="ch1",
            order=i,
            title=f"页 {i}",
            message="结论",
        )
        for i in range(4)
    ]

    issues = AutomatedReviewService(db_session).run_architectural_review(
        presentation_id,  # type: ignore[arg-type]
        slides,
        brief=brief,
    )

    assert any(issue.category == ReviewCategory.STRUCTURE for issue in issues)
    assert any(issue.severity == ReviewSeverity.MEDIUM for issue in issues)
    assert all(issue.reviewer_layer == ReviewLayer.ARCHITECTURAL for issue in issues)


def test_architectural_review_llm_when_enabled(
    db_session: Session,
    presentation_id: object,
) -> None:
    from archium.config.settings import Settings
    from archium.infrastructure.llm import MockLLMProvider

    from tests.fixtures.mock_llm import pipeline_mock_selector

    slides = [
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="ch1",
            order=0,
            title="院区现状",
            message="交通组织存在问题",
        ),
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="ch1",
            order=1,
            title="核心问题",
            message="人车混行",
        ),
    ]
    settings = Settings(
        _env_file=None,
        llm_api_key="test-key",
        llm_professional_review_enabled=True,
    )
    llm = MockLLMProvider(selector=pipeline_mock_selector)
    issues = AutomatedReviewService(
        db_session,
        llm=llm,
        settings=settings,
    ).run_layout_review(presentation_id, slides)  # type: ignore[arg-type]

    assert len(llm.calls) == 1
    layers = {issue.reviewer_layer for issue in issues}
    assert ReviewLayer.CONTENT in layers
    assert ReviewLayer.EVIDENCE in layers
    assert ReviewLayer.LAYOUT in layers
    assert len(layers) >= 3


def test_brief_alignment_llm_flags_semantic_gap(
    db_session: Session,
    presentation_id: object,
) -> None:
    from archium.config.settings import Settings
    from archium.infrastructure.llm import MockLLMProvider

    from tests.fixtures.mock_llm import pipeline_mock_selector

    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,  # type: ignore[arg-type]
        title="概念汇报",
        audience="管理层",
        purpose="确认方向",
        core_message="通过交通重组与公共空间提升改善体验",
        required_sections=["现状分析", "改造策略"],
        decisions_required=["确认分期策略"],
    )
    slides = [
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="ch1",
            order=0,
            title="交通问题",
            message="人车混行导致效率低",
        )
    ]
    settings = Settings(
        _env_file=None,
        llm_api_key="test-key",
        llm_professional_review_enabled=True,
    )
    llm = MockLLMProvider(selector=pipeline_mock_selector)
    issues = AutomatedReviewService(
        db_session,
        llm=llm,
        settings=settings,
    ).run_content_review(presentation_id, slides, brief=brief)  # type: ignore[arg-type]

    assert len(llm.calls) == 1
    assert any(issue.title == "Brief 语义对齐不足" for issue in issues)
    assert all(issue.reviewer_layer == ReviewLayer.CONTENT for issue in issues if "Brief" in issue.title)


def test_brief_alignment_llm_passes_when_aligned(
    db_session: Session,
    presentation_id: object,
) -> None:
    from archium.config.settings import Settings
    from archium.infrastructure.llm import MockLLMProvider

    from tests.fixtures.mock_llm import brief_alignment_ok_selector

    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,  # type: ignore[arg-type]
        title="概念汇报",
        audience="管理层",
        purpose="确认方向",
        core_message="通过交通重组改善体验",
    )
    slides = [
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="ch1",
            order=0,
            title="交通重组",
            message="通过交通重组改善院区体验",
        )
    ]
    settings = Settings(
        _env_file=None,
        llm_api_key="test-key",
        llm_professional_review_enabled=True,
    )
    llm = MockLLMProvider(selector=brief_alignment_ok_selector)
    issues = AutomatedReviewService(
        db_session,
        llm=llm,
        settings=settings,
    ).run_content_review(presentation_id, slides, brief=brief)  # type: ignore[arg-type]

    assert len(llm.calls) == 1
    assert not any("Brief" in issue.title for issue in issues)


def test_evidence_review_flags_missing_visual_evidence(
    db_session: Session,
    presentation_id: object,
) -> None:
    slide = SlideSpec(
        presentation_id=presentation_id,  # type: ignore[arg-type]
        chapter_id="ch1",
        order=0,
        title="效果展示",
        message="主入口形象显著提升",
        visual_requirements=[
            VisualRequirement(type=VisualType.RENDERING, description="鸟瞰效果图", required=True)
        ],
    )

    issues = AutomatedReviewService(db_session).run_evidence_review(
        presentation_id,  # type: ignore[arg-type]
        [slide],
    )

    assert any(issue.title == "结论缺少视觉证据" for issue in issues)


def test_evidence_review_flags_weak_visual_message_link(
    db_session: Session,
    presentation_id: object,
) -> None:
    slide = SlideSpec(
        presentation_id=presentation_id,  # type: ignore[arg-type]
        chapter_id="ch1",
        order=0,
        title="住院规模",
        message="住院部床位紧张需扩容",
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PLAN,
                description="总平面图标注交通流线",
                required=True,
                preferred_asset_ids=[uuid4()],
                confirmed=True,
            )
        ],
    )

    issues = AutomatedReviewService(db_session).run_evidence_review(
        presentation_id,  # type: ignore[arg-type]
        [slide],
    )

    assert any(issue.title == "视觉素材与结论关联性弱" for issue in issues)


def test_architectural_review_flags_flow_color_legend(
    db_session: Session,
    presentation_id: object,
) -> None:
    slide = SlideSpec(
        presentation_id=presentation_id,  # type: ignore[arg-type]
        chapter_id="ch1",
        order=0,
        title="交通组织",
        message="优化院区车行与人行流线",
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PLAN,
                description="总平面图标注交通流线",
                required=True,
            )
        ],
    )

    issues = AutomatedReviewService(db_session).run_architectural_review(
        presentation_id,  # type: ignore[arg-type]
        [slide],
    )

    assert any(issue.title == "交通流线图缺少颜色图例提示" for issue in issues)


def test_architectural_review_flags_construction_detail_in_concept_brief(
    db_session: Session,
    presentation_id: object,
) -> None:
    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,  # type: ignore[arg-type]
        title="Brief",
        presentation_type=PresentationType.CONCEPT,
        audience="管理层",
        purpose="决策",
        duration_minutes=20,
        target_slide_count=8,
        core_message="核心",
    )
    slide = SlideSpec(
        presentation_id=presentation_id,  # type: ignore[arg-type]
        chapter_id="ch1",
        order=0,
        title="结构策略",
        message="柱配筋采用标准做法",
    )

    issues = AutomatedReviewService(db_session).run_architectural_review(
        presentation_id,  # type: ignore[arg-type]
        [slide],
        brief=brief,
    )

    assert any(issue.title == "概念汇报包含施工图级细节" for issue in issues)


def test_layout_review_flags_text_density_and_extreme_aspect_ratio(
    db_session: Session,
    presentation_id: object,
) -> None:
    from archium.domain.asset import Asset
    from archium.domain.enums import AssetType
    from archium.infrastructure.database.repositories import AssetRepository

    project = ProjectRepository(db_session).create(
        Project(name="Layout Review", project_type=ProjectType.HEALTHCARE)
    )
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            filename="panorama.jpg",
            path="/tmp/panorama.jpg",
            asset_type=AssetType.PHOTO,
            width=3000,
            height=500,
        )
    )
    slide = SlideSpec(
        presentation_id=presentation_id,  # type: ignore[arg-type]
        chapter_id="ch1",
        order=0,
        title="综合结论",
        message="这是一段较长的核心结论用于测试版面密度" * 12,
        key_points=[f"要点描述内容 {index}" * 4 for index in range(5)],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="全景照片",
                required=True,
                preferred_asset_ids=[asset.id],
            )
        ],
    )

    issues = AutomatedReviewService(db_session).run_layout_review(
        presentation_id,  # type: ignore[arg-type]
        [slide],
        project_id=project.id,
    )

    assert any(issue.title == "页面信息密度过高" for issue in issues)
    assert any(issue.title == "素材宽高比极端" for issue in issues)
    density_issue = next(issue for issue in issues if issue.title == "页面信息密度过高")
    assert density_issue.rule_code == ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY
    assert density_issue.auto_fixable is True
