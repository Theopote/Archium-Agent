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
        repaired = LayoutRepairService().repair(plan, report, design).plan
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
        repaired = LayoutRepairService().repair(plan, report, design).plan
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
        repaired = LayoutRepairService().repair(plan, report, design).plan
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
        repaired = LayoutRepairService().repair(plan, report, design).plan
        source = repaired.element_by_id("source")
        assert source is not None
        # Size-based: footnote (9) is the smallest token > 6 that meets min_source (8),
        # not a hard-coded source→caption name hop.
        assert source.style_token == "footnote"
        assert source.font_size_override is None
        assert not LayoutValidationService().validate(
            repaired, design, require_source=True
        ).issues_for(LAYOUT_FONT_TOO_SMALL)

    def test_font_upgrade_uses_actual_sizes_not_token_names(self) -> None:
        """When source is larger than footnote, upgrade must not hop source→caption by name."""
        design = default_presentation_design_system()
        # Invert the usual assumption: source 11pt, footnote 7pt (below min).
        typography = design.typography.model_copy(
            update={
                "source": design.typography.source.model_copy(update={"font_size": 11}),
                "footnote": design.typography.footnote.model_copy(update={"font_size": 7}),
            }
        )
        design = design.model_copy(update={"typography": typography})
        plan = _plan(
            LayoutElement(
                id="note",
                role=LayoutElementRole.SOURCE,
                content_type=LayoutContentType.TEXT,
                text_content="脚注",
                x=0.7,
                y=5.2,
                width=3,
                height=0.2,
                style_token="footnote",
            )
        )
        report = LayoutValidationService().validate(plan, design, require_source=True)
        assert report.issues_for(LAYOUT_FONT_TOO_SMALL)
        repaired = LayoutRepairService().repair(plan, report, design).plan
        note = repaired.element_by_id("note")
        assert note is not None
        # Smallest legal larger token is source (11), not caption via name map.
        assert note.style_token == "source"
        assert design.typography.source.font_size >= design.thresholds.min_source_font_pt

    def test_font_upgrade_override_when_no_larger_token(self) -> None:
        design = default_presentation_design_system()
        # Collapse every token below body minimum so only override can fix body text.
        tiny_tokens = {
            name: getattr(design.typography, name).model_copy(update={"font_size": 10})
            for name in (
                "display",
                "title",
                "subtitle",
                "heading",
                "body",
                "caption",
                "metric",
                "footnote",
                "source",
            )
        }
        design = design.model_copy(
            update={"typography": design.typography.model_copy(update=tiny_tokens)}
        )
        plan = _plan(
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="正文",
                x=0.7,
                y=1.0,
                width=4,
                height=0.5,
                style_token="body",
            )
        )
        report = LayoutValidationService().validate(plan, design, require_source=False)
        assert report.issues_for(LAYOUT_FONT_TOO_SMALL)
        repaired = LayoutRepairService().repair(plan, report, design).plan
        body = repaired.element_by_id("body")
        assert body is not None
        assert body.font_size_override == design.thresholds.min_body_font_pt
        assert not LayoutValidationService().validate(
            repaired, design, require_source=False
        ).issues_for(LAYOUT_FONT_TOO_SMALL)

    def test_compact_tokens_never_increase_font_size(self) -> None:
        from archium.domain.visual.text_style import smaller_compliant_tokens

        design = default_presentation_design_system()
        element = LayoutElement(
            id="body",
            role=LayoutElementRole.BODY_TEXT,
            content_type=LayoutContentType.TEXT,
            text_content="x",
            x=0.7,
            y=1.0,
            width=2,
            height=0.4,
            style_token="body",
        )
        smaller = smaller_compliant_tokens(
            element,
            typography=design.typography,
            minimum_pt=design.thresholds.min_body_font_pt,
        )
        body_size = design.typography.body.font_size
        for name in smaller:
            assert getattr(design.typography, name).font_size < body_size
            assert getattr(design.typography, name).font_size >= design.thresholds.min_body_font_pt
        # body→subtitle would be an *increase* and must not appear.
        assert "subtitle" not in smaller

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
        repaired = LayoutRepairService().repair(plan, report, design).plan
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
        repaired = LayoutRepairService().repair(plan, overflow_only, design).plan
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
        repaired = LayoutRepairService().repair(plan, report, design).plan
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
        repaired = LayoutRepairService().repair(plan, report, design).plan
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
        repaired = LayoutRepairService().repair(plan, report, design).plan
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
        repaired = LayoutRepairService().repair(plan, report, design).plan
        widths = [el.width for el in repaired.elements_by_role(LayoutElementRole.METRIC)]
        assert max(widths) - min(widths) < 1e-6
        assert not LayoutValidationService().validate(
            repaired, design, require_source=False
        ).issues_for(LAYOUT_INCONSISTENT_ALIGNMENT)


class TestLayoutRepairContracts:
    """Repair contracts: reading_order, hero reflow, before/after diffs."""

    def test_overlap_moves_later_reading_order_not_lower_y(self) -> None:
        """Later reading_order element moves even when it sits higher on the page."""
        from archium.domain.visual.enums import LayoutIssueSeverity
        from archium.domain.visual.validation import LayoutValidationIssue, LayoutValidationReport

        design = default_presentation_design_system()
        # a: earlier in reading_order but lower on page (larger y)
        # b: later in reading_order but higher on page (smaller y)
        plan = _plan(
            LayoutElement(
                id="a",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="Earlier",
                x=1.0,
                y=2.0,
                width=3.0,
                height=1.5,
                style_token="body",
            ),
            LayoutElement(
                id="b",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="Later",
                x=2.0,
                y=1.0,
                width=3.0,
                height=1.5,
                style_token="body",
            ),
        )
        assert plan.reading_order == ["a", "b"]
        a_before = plan.element_by_id("a")
        assert a_before is not None
        a_geom = (a_before.x, a_before.y, a_before.width, a_before.height)

        report = LayoutValidationReport(
            issues=[
                LayoutValidationIssue(
                    rule_code=LAYOUT_ELEMENT_OVERLAP,
                    severity=LayoutIssueSeverity.ERROR,
                    element_ids=["a", "b"],
                    message="forced overlap",
                    auto_repairable=True,
                )
            ],
            score=0.2,
        )
        result = LayoutRepairService().repair(plan, report, design)
        repaired = result.plan
        a = repaired.element_by_id("a")
        b = repaired.element_by_id("b")
        assert a is not None and b is not None
        # Earlier reader stays put; later reader is the mover.
        assert (a.x, a.y, a.width, a.height) == a_geom
        assert b.y >= a.bottom - 1e-6 or b.x >= a.right - 1e-6
        assert list(repaired.reading_order) == ["a", "b"]
        assert result.reading_order_preserved

    def test_hero_enlarge_reflows_supporting_body(self) -> None:
        design = default_presentation_design_system()
        plan = _plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=0.7,
                y=0.45,
                width=8.0,
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
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="Supporting copy that will be covered by an enlarged hero.",
                x=1.0,
                y=1.5,
                width=4.0,
                height=1.2,
                style_token="body",
            ),
            family=LayoutFamily.DRAWING_FOCUS,
        )
        report = LayoutValidationService().validate(plan, design, drawing_hero=True)
        assert report.issues_for(LAYOUT_HERO_NOT_DOMINANT)
        result = LayoutRepairService().repair(plan, report, design)
        hero = result.plan.element_by_id("hero")
        body = result.plan.element_by_id("body")
        assert hero is not None and body is not None
        assert hero.area > 2.0
        # Supporting body must not remain inside the enlarged hero.
        assert body.y >= hero.bottom - 1e-6 or body.x >= hero.right - 1e-6
        assert list(result.plan.reading_order) == list(plan.reading_order)
        assert result.reading_order_preserved
        assert any(item.element_id == "hero" for item in result.diffs)
        assert any(item.element_id == "body" for item in result.diffs)

    def test_repair_records_before_after_diffs(self) -> None:
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
        report = LayoutValidationService().validate(plan, design)
        assert report.issues_for(LAYOUT_ELEMENT_OUTSIDE_PAGE)
        result = LayoutRepairService().repair(plan, report, design)
        assert result.diffs
        title_diff = next(item for item in result.diffs if item.element_id == "title")
        assert "x" in title_diff.changed_fields or "width" in title_diff.changed_fields
        assert title_diff.before["x"] != title_diff.after["x"] or (
            title_diff.before["width"] != title_diff.after["width"]
        )
        payload = result.to_log_dict()
        assert payload["diff_count"] == len(result.diffs)
        assert payload["reading_order_preserved"] is True
