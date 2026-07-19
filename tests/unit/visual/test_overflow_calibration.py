"""Overflow validation/repair calibration against real font metrics."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.layout_repair_service import LayoutRepairService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.domain.visual import default_presentation_design_system
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.validation import LAYOUT_TEXT_OVERFLOW
from archium.infrastructure.layout.font_resolver import fonts_available
from archium.infrastructure.layout.text_measurement import TextMeasurementService


def _text_plan(*elements: LayoutElement) -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="lead_and_points",
        page_width=10,
        page_height=5.625,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        elements=list(elements),
    )


def test_validation_tolerance_suppresses_sub_point_overflow() -> None:
    if not fonts_available():
        pytest.skip("System fonts unavailable")
    design = default_presentation_design_system()
    style = design.typography.body
    text = "临界排版测试：2026年Q1。"
    service = TextMeasurementService()
    needed = service.estimate_block_height_in(text, box_width_in=2.0, style=style)
    tolerance = design.thresholds.text_overflow_validation_tolerance_in
    box_height = needed - tolerance * 0.5
    assert service.overflow_amount(
        text,
        box_width_in=2.0,
        box_height_in=box_height,
        style=style,
        vertical_tolerance_in=tolerance,
    ) <= 0
    assert service.overflow_amount(
        text,
        box_width_in=2.0,
        box_height_in=box_height - tolerance * 2,
        style=style,
        vertical_tolerance_in=tolerance,
    ) > 0


def test_repair_slack_clears_validation_after_fix() -> None:
    design = default_presentation_design_system()
    plan = _text_plan(
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
    validator = LayoutValidationService()
    report = validator.validate(plan, design, require_source=False)
    assert report.issues_for(LAYOUT_TEXT_OVERFLOW)
    repaired = LayoutRepairService(validator._text).repair(plan, report, design).plan
    body = repaired.element_by_id("body")
    assert body is not None
    assert not validator.validate(repaired, design, require_source=False).issues_for(
        LAYOUT_TEXT_OVERFLOW
    )


def test_layout_threshold_defaults_are_calibrated() -> None:
    thresholds = default_presentation_design_system().thresholds
    assert thresholds.text_overflow_validation_tolerance_in == pytest.approx(0.012)
    assert thresholds.text_overflow_repair_slack_in == pytest.approx(0.020)
    assert thresholds.text_overflow_repair_slack_in > thresholds.text_overflow_validation_tolerance_in
