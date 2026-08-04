"""Evidence board hierarchical layout + hero hard-gate tests."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.domain.enums import SlideType, VisualType
from archium.domain.slide import SlideSpec
from archium.domain.slide import VisualRequirement as SlideVisualRequirement
from archium.domain.visual import (
    LayoutFamily,
    LayoutIssueSeverity,
    VisualContentType,
    VisualIntent,
    default_presentation_design_system,
)
from archium.domain.visual.validation import (
    LAYOUT_HERO_NOT_DOMINANT,
)
from archium.infrastructure.layout.generators.base import LayoutGeneratorContext, content_from_slide
from archium.infrastructure.layout.geometry import safe_area
from archium.infrastructure.layout.layout_solver import LayoutSolver


def _evidence_context(*, photo_count: int = 3) -> LayoutGeneratorContext:
    photos = [uuid4() for _ in range(photo_count)]
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="problem",
        order=2,
        title="现场问题证据",
        message="急诊流线交叉导致拥堵，需优先疏解。",
        slide_type=SlideType.IMAGE,
        key_points=[f"问题 {i + 1}" for i in range(photo_count)],
        visual_requirements=[
            SlideVisualRequirement(
                type=VisualType.SITE_PHOTO,
                description=f"现场{i + 1}",
                preferred_asset_ids=[photos[i]],
            )
            for i in range(photo_count)
        ],
    )
    intent = VisualIntent(
        slide_id=slide.id,
        communication_goal="证据",
        audience_takeaway=slide.message,
        visual_priority="photos > conclusion",
        dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
        preferred_layout_families=[LayoutFamily.EVIDENCE_BOARD],
        hero_asset_id=photos[0],
        supporting_asset_ids=photos[1:],
    )
    design = default_presentation_design_system()
    return LayoutGeneratorContext(
        slide=slide,
        visual_intent=intent,
        art_direction=None,
        design_system=design,
        content=content_from_slide(slide, intent),
        variant="hierarchical",
    )


def test_evidence_board_hierarchical_primary_larger_than_aux() -> None:
    ctx = _evidence_context(photo_count=3)
    plan = LayoutSolver().generate(LayoutFamily.EVIDENCE_BOARD, ctx)
    assert plan.balance_strategy == "evidence_hierarchy"
    photos = [el for el in plan.elements if el.id.startswith("photo_")]
    assert len(photos) == 3
    primary = plan.element_by_id("photo_0")
    aux1 = plan.element_by_id("photo_1")
    assert primary is not None and aux1 is not None
    assert primary.area > aux1.area
    lead = plan.element_by_id("lead")
    assert lead is not None
    safe = safe_area(ctx.design_system)
    assert lead.area / safe.area >= 0.08
    annotations = [el for el in plan.elements if el.id.startswith("annotation_")]
    assert len(annotations) == 3
    assert annotations[0].text_content and annotations[0].text_content.startswith("1.")


def test_hero_not_dominant_is_error() -> None:
    from archium.domain.visual.enums import (
        CropPolicy,
        ImageFit,
        LayoutContentType,
        LayoutElementRole,
        LayoutValidationStatus,
    )
    from archium.domain.visual.layout import LayoutElement, LayoutPlan

    design = default_presentation_design_system()
    intent_id = uuid4()
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="split",
        page_width=design.page.width,
        page_height=design.page.height,
        hero_element_id="hero",
        reading_order=["title", "hero"],
        whitespace_ratio=0.4,
        balance_strategy="image_dominant",
        validation_status=LayoutValidationStatus.PENDING,
        design_system_id=design.id,
        visual_intent_id=intent_id,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="封面",
                x=0.7,
                y=0.45,
                width=8,
                height=0.5,
                style_token="title",
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=6.5,
                y=1.5,
                width=2.5,
                height=2.0,
                fit_mode=ImageFit.COVER,
                crop_policy=CropPolicy.COVER_CROP,
            ),
        ],
    )
    report = LayoutValidationService().validate(plan, design)
    issues = report.issues_for(LAYOUT_HERO_NOT_DOMINANT)
    assert issues
    assert issues[0].severity == LayoutIssueSeverity.ERROR
    assert not report.valid


def test_hero_full_bleed_passes_hard_dominance() -> None:
    photos = uuid4()
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="cover",
        order=0,
        title="项目封面",
        message="以一张主视觉建立汇报记忆点。",
        visual_requirements=[
            SlideVisualRequirement(type=VisualType.RENDERING, description="hero")
        ],
    )
    intent = VisualIntent(
        slide_id=slide.id,
        communication_goal="封面",
        audience_takeaway=slide.message,
        visual_priority="hero",
        dominant_content_type=VisualContentType.HERO_IMAGE,
        preferred_layout_families=[LayoutFamily.HERO],
        hero_asset_id=photos,
    )
    design = default_presentation_design_system()
    ctx = LayoutGeneratorContext(
        slide=slide,
        visual_intent=intent,
        art_direction=None,
        design_system=design,
        content=content_from_slide(slide, intent),
        variant="full_bleed",
    )
    plan = LayoutSolver().generate(LayoutFamily.HERO, ctx)
    report = LayoutValidationService().validate(plan, design)
    assert not report.issues_for(LAYOUT_HERO_NOT_DOMINANT)
