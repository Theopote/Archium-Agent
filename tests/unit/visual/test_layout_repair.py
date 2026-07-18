"""Unit tests for LayoutRepairService auto-repair coverage."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.layout_repair_service import LayoutRepairService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.domain.visual import (
    LAYOUT_DRAWING_CROPPED,
    LAYOUT_ELEMENT_OUTSIDE_PAGE,
    LAYOUT_ELEMENT_OVERLAP,
    LAYOUT_FONT_TOO_SMALL,
    LAYOUT_HERO_NOT_DOMINANT,
    LAYOUT_IMAGE_DISTORTION,
    LAYOUT_INCONSISTENT_ALIGNMENT,
    LAYOUT_TEXT_OVERFLOW,
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
    default_presentation_design_system,
)
from archium.domain.visual.enums import (
    CropPolicy,
    ImageFit,
    LayoutContentType,
    LayoutValidationStatus,
    OverflowPolicy,
)


def _plan(*elements: LayoutElement, family: LayoutFamily = LayoutFamily.HERO) -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        layout_family=family,
        layout_variant="split",
        page_width=10,
        page_height=5.625,
        hero_element_id="hero" if any(el.id == "hero" for el in elements) else None,
        reading_order=[el.id for el in elements],
        whitespace_ratio=0.3,
        elements=list(elements),
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )


class TestLayoutRepairService:
    def test_repairs_outside_page(self) -> None:
        design = default_presentation_design_system()
        plan = _plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=9.5,
                y=0.4,
                width=2.0,
                height=0.5,
                style_token="title",
            )
        )
        validator = LayoutValidationService()
        report = validator.validate(plan, design)
        assert report.issues_for(LAYOUT_ELEMENT_OUTSIDE_PAGE)
        repaired = LayoutRepairService().repair(plan, report, design)
        assert repaired.validation_status == LayoutValidationStatus.REPAIRED
        title = repaired.element_by_id("title")
        assert title is not None
        assert title.x + title.width <= plan.page_width + 1e-6
        assert not validator.validate(repaired, design).issues_for(LAYOUT_ELEMENT_OUTSIDE_PAGE)

    def test_repairs_overlap(self) -> None:
        design = default_presentation_design_system()
        plan = _plan(
            LayoutElement(
                id="a",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="A",
                x=1,
                y=1,
                width=3,
                height=2,
                style_token="body",
            ),
            LayoutElement(
                id="b",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="B",
                x=2,
                y=1.5,
                width=3,
                height=2,
                style_token="body",
            ),
        )
        report = LayoutValidationService().validate(plan, design)
        assert report.issues_for(LAYOUT_ELEMENT_OVERLAP)
        repaired = LayoutRepairService().repair(plan, report, design)
        b = repaired.element_by_id("b")
        a = repaired.element_by_id("a")
        assert a is not None and b is not None
        assert b.y >= a.bottom - 1e-6 or b.x >= a.right - 1e-6
        assert not LayoutValidationService().validate(repaired, design).issues_for(
            LAYOUT_ELEMENT_OVERLAP
        )

    def test_repairs_overlap_prefers_unlocked(self) -> None:
        design = default_presentation_design_system()
        plan = _plan(
            LayoutElement(
                id="locked",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=1,
                y=1,
                width=4,
                height=3,
                locked=True,
            ),
            LayoutElement(
                id="text",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="说明",
                x=2,
                y=2,
                width=3,
                height=1.5,
                style_token="body",
            ),
        )
        report = LayoutValidationService().validate(plan, design)
        repaired = LayoutRepairService().repair(plan, report, design)
        locked = repaired.element_by_id("locked")
        text = repaired.element_by_id("text")
        assert locked is not None and text is not None
        assert locked.x == 1 and locked.y == 1
        assert text.y >= locked.bottom - 1e-6 or text.x >= locked.right - 1e-6

    def test_repairs_font_too_small(self) -> None:
        design = default_presentation_design_system()
        tiny = design.typography.source.model_copy(update={"font_size": 6})
        design = design.model_copy(
            update={"typography": design.typography.model_copy(update={"source": tiny})}
        )
        plan = _plan(
            LayoutElement(
                id="source",
                role=LayoutElementRole.SOURCE,
                content_type=LayoutContentType.TEXT,
                text_content="来源",
                x=0.7,
                y=5.2,
                width=3,
                height=0.2,
                style_token="source",
            )
        )
        report = LayoutValidationService().validate(plan, design, require_source=True)
        assert report.issues_for(LAYOUT_FONT_TOO_SMALL)
        repaired = LayoutRepairService().repair(plan, report, design)
        source = repaired.element_by_id("source")
        assert source is not None
        assert source.style_token == "caption"
        assert not LayoutValidationService().validate(
            repaired, design, require_source=True
        ).issues_for(LAYOUT_FONT_TOO_SMALL)

    def test_repairs_text_overflow(self) -> None:
        design = default_presentation_design_system()
        plan = _plan(
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="这是一段非常长的正文" * 40,
                x=0.7,
                y=1.0,
                width=2.0,
                height=0.4,
                style_token="body",
            )
        )
        report = LayoutValidationService().validate(plan, design, require_source=False)
        assert report.issues_for(LAYOUT_TEXT_OVERFLOW)
        repaired = LayoutRepairService().repair(plan, report, design)
        body = repaired.element_by_id("body")
        assert body is not None
        assert body.height > 0.4 or body.width > 2.0
        # Must not casually claim the entire safe area.
        from archium.infrastructure.layout.geometry import safe_area as safe_rect

        safe = safe_rect(design)
        assert body.area < safe.area * 0.95
        assert not LayoutValidationService().validate(
            repaired, design, require_source=False
        ).issues_for(LAYOUT_TEXT_OVERFLOW)

    def test_text_overflow_does_not_cover_unlocked_neighbors(self) -> None:
        """P0: overflow repair must not paint over unlocked hero/body/metrics."""
        design = default_presentation_design_system()
        plan = _plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=4.5,
                y=1.0,
                width=4.8,
                height=3.5,
                locked=False,
            ),
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="溢出正文需要更多空间" * 12,
                x=0.7,
                y=1.0,
                width=2.0,
                height=0.35,
                style_token="body",
            ),
            family=LayoutFamily.HERO,
        )
        report = LayoutValidationService().validate(plan, design, require_source=False)
        assert report.issues_for(LAYOUT_TEXT_OVERFLOW)
        # Repair only the overflow issue so hero geometry stays put for this assertion.
        overflow_only = report.model_copy(
            update={"issues": list(report.issues_for(LAYOUT_TEXT_OVERFLOW))}
        )
        repaired = LayoutRepairService().repair(plan, overflow_only, design)
        body = repaired.element_by_id("body")
        hero = repaired.element_by_id("hero")
        assert body is not None and hero is not None
        assert hero.x == 4.5 and hero.y == 1.0 and hero.width == 4.8
        # No overlap with the unlocked neighbor.
        assert (
            body.right <= hero.x + 1e-6
            or body.bottom <= hero.y + 1e-6
            or body.y >= hero.bottom - 1e-6
            or body.x >= hero.right - 1e-6
        )
        assert body.width < 8.0  # did not snap to full safe width

    def test_text_overflow_unresolved_suggests_split_and_variant(self) -> None:
        """When text cannot fit without covering neighbors, escalate — don't fill safe."""
        design = default_presentation_design_system()
        plan = _plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=0.7,
                y=1.0,
                width=8.6,
                height=3.5,
                locked=False,
            ),
            LayoutElement(
                id="caption",
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                text_content="极窄缝隙中的超长说明文字" * 30,
                x=0.7,
                y=4.55,
                width=8.6,
                height=0.25,
                style_token="caption",
            ),
            family=LayoutFamily.HERO,
        )
        before_variant = plan.layout_variant
        report = LayoutValidationService().validate(plan, design, require_source=False)
        assert report.issues_for(LAYOUT_TEXT_OVERFLOW)
        repaired = LayoutRepairService().repair(plan, report, design)
        caption = repaired.element_by_id("caption")
        hero = repaired.element_by_id("hero")
        assert caption is not None and hero is not None
        # Must not cover the hero by claiming the safe area.
        assert caption.height <= 0.5
        assert caption.y + 1e-6 >= hero.bottom or caption.bottom <= hero.y + 1e-6
        assert repaired.overflow_policy == OverflowPolicy.SPLIT
        assert repaired.layout_variant != before_variant

    def test_repairs_drawing_crop_and_distortion(self) -> None:
        design = default_presentation_design_system()
        plan = _plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                x=0.7,
                y=1.2,
                width=8,
                height=3.5,
                fit_mode=ImageFit.FILL,
                crop_policy=CropPolicy.COVER_CROP,
            ),
            family=LayoutFamily.DRAWING_FOCUS,
        )
        report = LayoutValidationService().validate(plan, design, drawing_hero=True)
        assert report.issues_for(LAYOUT_DRAWING_CROPPED) or report.issues_for(
            LAYOUT_IMAGE_DISTORTION
        )
        repaired = LayoutRepairService().repair(plan, report, design)
        hero = repaired.element_by_id("hero")
        assert hero is not None
        assert hero.fit_mode == ImageFit.CONTAIN
        assert hero.crop_policy == CropPolicy.FORBIDDEN

    def test_repairs_hero_not_dominant(self) -> None:
        design = default_presentation_design_system()
        plan = _plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=0.7,
                y=0.45,
                width=8,
                height=0.5,
                style_token="title",
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                x=0.7,
                y=1.2,
                width=2.0,
                height=1.0,
                fit_mode=ImageFit.CONTAIN,
                crop_policy=CropPolicy.FORBIDDEN,
                locked=True,
            ),
            family=LayoutFamily.DRAWING_FOCUS,
        )
        report = LayoutValidationService().validate(plan, design, drawing_hero=True)
        assert report.issues_for(LAYOUT_HERO_NOT_DOMINANT)
        before = plan.element_by_id("hero")
        assert before is not None
        repaired = LayoutRepairService().repair(plan, report, design)
        hero = repaired.element_by_id("hero")
        assert hero is not None
        assert hero.area > before.area
        assert not LayoutValidationService().validate(
            repaired, design, drawing_hero=True
        ).issues_for(LAYOUT_HERO_NOT_DOMINANT)

    def test_repairs_inconsistent_alignment(self) -> None:
        design = default_presentation_design_system()
        plan = _plan(
            LayoutElement(
                id="m0",
                role=LayoutElementRole.METRIC,
                content_type=LayoutContentType.METRIC,
                text_content="A",
                x=0.7,
                y=1.2,
                width=2.0,
                height=1.0,
                style_token="metric",
            ),
            LayoutElement(
                id="m1",
                role=LayoutElementRole.METRIC,
                content_type=LayoutContentType.METRIC,
                text_content="B",
                x=3.5,
                y=1.5,
                width=2.8,
                height=1.0,
                style_token="metric",
            ),
            LayoutElement(
                id="m2",
                role=LayoutElementRole.METRIC,
                content_type=LayoutContentType.METRIC,
                text_content="C",
                x=6.5,
                y=1.8,
                width=2.2,
                height=1.0,
                style_token="metric",
            ),
            family=LayoutFamily.METRIC_DASHBOARD,
        )
        report = LayoutValidationService().validate(plan, design, require_source=False)
        assert report.issues_for(LAYOUT_INCONSISTENT_ALIGNMENT)
        repaired = LayoutRepairService().repair(plan, report, design)
        widths = [el.width for el in repaired.elements_by_role(LayoutElementRole.METRIC)]
        assert max(widths) - min(widths) < 1e-6
        assert not LayoutValidationService().validate(
            repaired, design, require_source=False
        ).issues_for(LAYOUT_INCONSISTENT_ALIGNMENT)
