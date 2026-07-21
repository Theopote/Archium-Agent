"""Unit tests for semantic content plan helpers."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.semantic_content_plan import (
    build_semantic_content_plan,
    build_slide_spec_from_outline_page,
    expand_visual_evidence_roles,
    expected_text_evidence_count,
)
from archium.domain.citation import Citation
from archium.domain.fact import ProjectFact
from archium.domain.presentation_manuscript import ManuscriptFact
from archium.domain.slide import SlideSpec
from archium.domain.slide_generation_context import SlideGenerationContext
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    ContentRequirement,
    ContentRole,
    VisualRequirement,
)
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
    OutlineTemplateCompatibility,
)


def test_expand_visual_evidence_roles_aligns_with_evidence_min_count() -> None:
    schema = ArchitecturalContentSchema(
        name="content/photo_analysis",
        page_purpose="证明现场问题",
        evidence_items=[
            ContentRequirement(
                role=ContentRole.EVIDENCE,
                required=True,
                min_count=3,
                max_count=4,
            )
        ],
        visual_evidence=[
            VisualRequirement(
                role="hero_image",
                required=True,
                min_count=1,
                max_count=1,
            )
        ],
    )
    roles = expand_visual_evidence_roles(schema)
    assert roles == ["hero_image", "supporting_image", "supporting_image"]
    assert expected_text_evidence_count(schema) == 3


def test_expand_visual_evidence_roles_honors_visual_min_count() -> None:
    schema = ArchitecturalContentSchema(
        name="content/photo_grid",
        page_purpose="展示多图",
        visual_evidence=[
            VisualRequirement(
                role="supporting_image",
                required=True,
                min_count=2,
                max_count=4,
            )
        ],
    )
    roles = expand_visual_evidence_roles(schema)
    assert roles == ["supporting_image", "supporting_image"]


def test_build_slide_spec_from_outline_page_dedupes_evidence() -> None:
    outline = OutlinePlan(
        presentation_id=uuid4(),
        title="汇报",
        thesis="t",
        audience="a",
        purpose="p",
        sections=[
            OutlineSection(
                id="problem",
                title="问题",
                purpose="说明现场问题与影响",
                key_message="人车冲突严重",
                order=0,
                category="problem",
                evidence_requirements=["高峰拥堵", "消防通道占用"],
            )
        ],
    )
    page = OutlineTemplateCompatibility(
        slide_id="problem__p01",
        section_id="problem",
        section_title="问题",
        fallback_mode="template_editing",
        inferred_functional_type=FunctionalSlideType.CONTENT,
        inferred_content_type=ArchitecturalContentType.PHOTO_ANALYSIS,
    )
    spec = build_slide_spec_from_outline_page(
        outline=outline,
        section=outline.sections[0],
        page=page,
    )
    assert spec.title == "问题"
    assert spec.message == "人车冲突严重"
    assert spec.key_points == ["高峰拥堵", "消防通道占用"]
    assert spec.speaker_notes == "说明现场问题与影响"


def test_build_semantic_content_plan_merges_generation_context() -> None:
    schema = ArchitecturalContentSchema(
        name="content/strategy",
        page_purpose="提出策略",
        evidence_items=[
            ContentRequirement(
                role=ContentRole.EVIDENCE,
                required=True,
                min_count=1,
                max_count=3,
            )
        ],
        interpretation=ContentRequirement(
            role=ContentRole.INTERPRETATION,
            required=True,
            max_count=1,
        ),
    )
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="strategy",
        order=0,
        title="策略",
        message="慢行优先",
        key_points=["保留街巷肌理"],
    )
    context = SlideGenerationContext(
        slide_spec=slide,
        section_summary="策略章节：以慢行优先组织空间。",
        verified_facts=[
            ManuscriptFact(
                statement="保留 3 条历史街巷",
                source_id="fact-1",
                verified=True,
            )
        ],
        project_facts=[
            ProjectFact(
                project_id=uuid4(),
                key="site_area",
                label="用地面积",
                value="12.5",
                unit="公顷",
            )
        ],
        relevant_citations=[
            Citation(
                document_id=uuid4(),
                document_name="任务书.pdf",
                page_number=5,
            )
        ],
    )
    plan = build_semantic_content_plan(schema, slide, generation_context=context)
    assert "保留 3 条历史街巷" in plan.evidence_labels
    assert any("用地面积" in label for label in plan.evidence_labels)
    assert plan.interpretation == "策略章节：以慢行优先组织空间。"
    assert plan.source == "任务书.pdf, p.5"
