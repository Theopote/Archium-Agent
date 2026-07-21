"""Unit tests for semantic content plan helpers."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.semantic_content_plan import (
    build_slide_spec_from_outline_page,
    expand_visual_evidence_roles,
    expected_text_evidence_count,
)
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
