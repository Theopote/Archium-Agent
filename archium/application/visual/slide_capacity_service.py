"""Estimate SlideCapacityBudget before LayoutPlan generation."""

from __future__ import annotations

from archium.domain.slide import SlideSpec
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import LayoutFamily, VisualContentType
from archium.domain.visual.slide_capacity_budget import (
    ADAPT_CONTENT_RATIO,
    OVERFLOW_RISK_FLOOR,
    OVERFLOW_RISK_SPAN,
    SPLIT_SLIDE_RATIO,
    CapacityRecommendedAction,
    SlideCapacityBudget,
)
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.geometry import safe_area
from archium.infrastructure.layout.text_measurement import TextMeasurementService

# Minimum image/drawing height as a fraction of usable height.
_IMAGE_HEIGHT_FRACTIONS: dict[LayoutFamily, float] = {
    LayoutFamily.DRAWING_FOCUS: 0.45,
    LayoutFamily.EVIDENCE_BOARD: 0.35,
    LayoutFamily.HERO: 0.40,
    LayoutFamily.ANALYTICAL_DIAGRAM: 0.40,
    LayoutFamily.COMPARATIVE_MATRIX: 0.30,
    LayoutFamily.HYBRID_CANVAS: 0.30,
    LayoutFamily.PROCESS_NARRATIVE: 0.25,
    LayoutFamily.METRIC_DASHBOARD: 0.15,
}

_DRAWING_CONTENT_TYPES = {
    VisualContentType.SITE_PLAN,
    VisualContentType.FLOOR_PLAN,
    VisualContentType.SECTION,
    VisualContentType.ELEVATION,
    VisualContentType.ANALYTICAL_DIAGRAM,
    VisualContentType.HERO_IMAGE,
    VisualContentType.PHOTO_EVIDENCE,
}

_ANNOTATION_STRIP_IN = 0.35


class SlideCapacityService:
    """Deterministic pre-layout capacity estimator (no LLM)."""

    def __init__(self, text_measurement: TextMeasurementService | None = None) -> None:
        self._text = text_measurement or TextMeasurementService()

    def estimate(
        self,
        slide: SlideSpec,
        design_system: DesignSystem,
        *,
        visual_intent: VisualIntent | None = None,
        layout_family: LayoutFamily | None = None,
    ) -> SlideCapacityBudget:
        safe = safe_area(design_system)
        usable_width = max(0.01, safe.width)
        usable_height = max(0.01, safe.height)

        text_height = self._estimate_text_height(
            slide,
            design_system,
            usable_width=usable_width,
        )
        image_height = self._image_height_budget(
            slide,
            usable_height=usable_height,
            visual_intent=visual_intent,
            layout_family=layout_family,
        )
        annotation_height = self._annotation_height_budget(
            image_height=image_height,
            visual_intent=visual_intent,
            layout_family=layout_family,
        )

        image_area = image_height * usable_width
        annotation_area = annotation_height * usable_width
        required_height = text_height + image_height + annotation_height
        capacity_ratio = required_height / usable_height
        overflow_risk = _clamp(
            (capacity_ratio - OVERFLOW_RISK_FLOOR) / OVERFLOW_RISK_SPAN,
            0.0,
            1.0,
        )
        action = _recommend_action(capacity_ratio)

        return SlideCapacityBudget(
            usable_width=usable_width,
            usable_height=usable_height,
            estimated_text_height=round(text_height, 4),
            image_area_required=round(image_area, 4),
            annotation_area_required=round(annotation_area, 4),
            capacity_ratio=round(capacity_ratio, 4),
            overflow_risk=round(overflow_risk, 4),
            recommended_action=action,
        )

    def _estimate_text_height(
        self,
        slide: SlideSpec,
        design_system: DesignSystem,
        *,
        usable_width: float,
    ) -> float:
        typography = design_system.typography
        # Title spans most of width; body uses a slightly narrower column heuristic.
        title_width = usable_width
        body_width = max(0.01, usable_width * 0.92)

        height = 0.0
        if slide.title.strip():
            height += self._text.estimate_block_height_in(
                slide.title,
                box_width_in=title_width,
                style=typography.title,
            )
        if slide.message.strip():
            height += self._text.estimate_block_height_in(
                slide.message,
                box_width_in=body_width,
                style=typography.body,
            )
        for point in slide.key_points:
            if not point.strip():
                continue
            height += self._text.estimate_block_height_in(
                f"• {point}",
                box_width_in=body_width,
                style=typography.body,
            )
        # Inter-block gaps
        blocks = 1 if slide.title.strip() else 0
        blocks += 1 if slide.message.strip() else 0
        blocks += sum(1 for point in slide.key_points if point.strip())
        if blocks > 1:
            height += design_system.spacing.sm * (blocks - 1)
        return height

    def _image_height_budget(
        self,
        slide: SlideSpec,
        *,
        usable_height: float,
        visual_intent: VisualIntent | None,
        layout_family: LayoutFamily | None,
    ) -> float:
        fraction = 0.0
        if layout_family is not None:
            fraction = max(fraction, _IMAGE_HEIGHT_FRACTIONS.get(layout_family, 0.0))
        if visual_intent is not None:
            content = visual_intent.dominant_content_type
            if content in _DRAWING_CONTENT_TYPES:
                fraction = max(fraction, 0.40)
            if content == VisualContentType.PHOTO_EVIDENCE:
                fraction = max(fraction, 0.35)
            if content in {
                VisualContentType.SITE_PLAN,
                VisualContentType.FLOOR_PLAN,
                VisualContentType.SECTION,
                VisualContentType.ELEVATION,
            }:
                fraction = max(fraction, 0.45)
        if slide.visual_requirements and fraction <= 0:
            fraction = 0.30
        return usable_height * fraction

    def _annotation_height_budget(
        self,
        *,
        image_height: float,
        visual_intent: VisualIntent | None,
        layout_family: LayoutFamily | None,
    ) -> float:
        needs_annotation = image_height > 0
        if layout_family in {
            LayoutFamily.DRAWING_FOCUS,
            LayoutFamily.ANALYTICAL_DIAGRAM,
        }:
            needs_annotation = True
        if visual_intent is not None and visual_intent.dominant_content_type in {
            VisualContentType.SITE_PLAN,
            VisualContentType.FLOOR_PLAN,
            VisualContentType.ANALYTICAL_DIAGRAM,
        }:
            needs_annotation = True
        return _ANNOTATION_STRIP_IN if needs_annotation else 0.0


def _recommend_action(capacity_ratio: float) -> CapacityRecommendedAction:
    if capacity_ratio > SPLIT_SLIDE_RATIO:
        return "split_slide"
    if capacity_ratio > ADAPT_CONTENT_RATIO:
        return "adapt_content"
    return "proceed"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
