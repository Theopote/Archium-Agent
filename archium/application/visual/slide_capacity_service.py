"""Estimate SlideCapacityBudget before LayoutPlan generation."""

from __future__ import annotations

import re

from archium.domain.slide import SlideSpec
from archium.domain.visual.design_system import DesignSystem, TextStyleToken
from archium.domain.visual.enums import LayoutFamily, VisualContentType
from archium.domain.visual.slide_capacity_budget import (
    ADAPT_CONTENT_RATIO,
    OVERFLOW_RISK_FLOOR,
    OVERFLOW_RISK_SPAN,
    SPLIT_SLIDE_RATIO,
    CapacityRecommendedAction,
    CapacityStatus,
    SlideCapacityBudget,
    capacity_status_for_ratio,
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
}

_PHOTO_CONTENT_TYPES = {
    VisualContentType.PHOTO_EVIDENCE,
    VisualContentType.HERO_IMAGE,
}

# Architectural drawings need a readable viewport — not just any image area.
_DRAWING_MIN_HEIGHT_FRACTION = 0.42
_DRAWING_MIN_WIDTH_FRACTION = 0.55
# Legend + north arrow + scale together (sq in relative to usable width strip).
_LEGEND_STRIP_HEIGHT_IN = 0.45
# Caption uses caption typography; floor when measuring empty captions.
_CAPTION_FLOOR_IN = 0.22
_ANNOTATION_BASE_STRIP_IN = 0.28
_ANNOTATION_DENSITY_BY_CONTENT: dict[VisualContentType, float] = {
    VisualContentType.SITE_PLAN: 0.75,
    VisualContentType.FLOOR_PLAN: 0.70,
    VisualContentType.SECTION: 0.55,
    VisualContentType.ELEVATION: 0.50,
    VisualContentType.ANALYTICAL_DIAGRAM: 0.65,
    VisualContentType.PHOTO_EVIDENCE: 0.25,
}

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")


class SlideCapacityService:
    """Deterministic pre-layout capacity estimator (no LLM).

    Text demand always goes through ``TextMeasurementService`` with an explicit
    ``TextStyleToken`` (family / size / weight / line_height) plus box width and
    language — never bare character-count heuristics at this layer.
    """

    def __init__(self, text_measurement: TextMeasurementService | None = None) -> None:
        self._text = text_measurement or TextMeasurementService()

    def estimate(
        self,
        slide: SlideSpec,
        design_system: DesignSystem,
        *,
        visual_intent: VisualIntent | None = None,
        layout_family: LayoutFamily | None = None,
        language: str | None = None,
    ) -> SlideCapacityBudget:
        safe = safe_area(design_system)
        usable_width = max(0.01, safe.width)
        usable_height = max(0.01, safe.height)
        text_language = language or detect_slide_language(slide)

        text_height = self._estimate_text_height(
            slide,
            design_system,
            usable_width=usable_width,
            language=text_language,
        )
        drawing = self._drawing_budgets(
            usable_width=usable_width,
            usable_height=usable_height,
            visual_intent=visual_intent,
            layout_family=layout_family,
        )
        image_height = self._image_height_budget(
            slide,
            usable_height=usable_height,
            visual_intent=visual_intent,
            layout_family=layout_family,
            drawing_min_height=drawing["min_readable_height"],
        )
        caption_height = self._caption_height_budget(
            slide,
            design_system,
            usable_width=usable_width,
            language=text_language,
            needs_caption=drawing["needs_drawing_chrome"] or image_height > 0,
        )
        legend_height = drawing["legend_height"]
        annotation_density = drawing["annotation_density"]
        annotation_height = self._annotation_height_budget(
            image_height=image_height,
            visual_intent=visual_intent,
            layout_family=layout_family,
            annotation_density=annotation_density,
            needs_drawing_chrome=drawing["needs_drawing_chrome"],
        )

        image_area = image_height * usable_width
        annotation_area = annotation_height * usable_width
        drawing_min_area = drawing["min_readable_height"] * usable_width
        legend_area = legend_height * usable_width

        required_height = (
            text_height
            + image_height
            + caption_height
            + legend_height
            + annotation_height
        )
        capacity_ratio = required_height / usable_height
        # Drawing alone cannot shrink below readable minimum → impossible.
        drawing_impossible = (
            drawing["needs_drawing_chrome"]
            and drawing["min_readable_height"] + caption_height + legend_height
            > usable_height + 1e-6
        )
        status = capacity_status_for_ratio(
            capacity_ratio,
            drawing_impossible=drawing_impossible,
        )
        overflow_risk = _clamp(
            (capacity_ratio - OVERFLOW_RISK_FLOOR) / OVERFLOW_RISK_SPAN,
            0.0,
            1.0,
        )
        action = _recommend_action(capacity_ratio, status)

        return SlideCapacityBudget(
            usable_width=usable_width,
            usable_height=usable_height,
            estimated_text_height=round(text_height, 4),
            image_area_required=round(image_area, 4),
            annotation_area_required=round(annotation_area, 4),
            drawing_min_readable_area=round(drawing_min_area, 4),
            caption_required_height=round(caption_height, 4),
            legend_required_area=round(legend_area, 4),
            annotation_density=round(annotation_density, 4),
            capacity_ratio=round(capacity_ratio, 4),
            overflow_risk=round(overflow_risk, 4),
            status=status,
            recommended_action=action,
            used_real_font_metrics=self._text.uses_real_metrics,
            text_language=text_language,
        )

    def _estimate_text_height(
        self,
        slide: SlideSpec,
        design_system: DesignSystem,
        *,
        usable_width: float,
        language: str,
    ) -> float:
        typography = design_system.typography
        title_width = usable_width
        body_width = max(0.01, usable_width * 0.92)

        height = 0.0
        if slide.title.strip():
            height += self._measure_styled(
                slide.title,
                box_width_in=title_width,
                style=typography.title,
                language=language,
            )
        if slide.message.strip():
            height += self._measure_styled(
                slide.message,
                box_width_in=body_width,
                style=typography.body,
                language=language,
            )
        for point in slide.key_points:
            if not point.strip():
                continue
            height += self._measure_styled(
                f"• {point}",
                box_width_in=body_width,
                style=typography.body,
                language=language,
            )
        blocks = 1 if slide.title.strip() else 0
        blocks += 1 if slide.message.strip() else 0
        blocks += sum(1 for point in slide.key_points if point.strip())
        if blocks > 1:
            height += design_system.spacing.sm * (blocks - 1)
        return height

    def _measure_styled(
        self,
        text: str,
        *,
        box_width_in: float,
        style: TextStyleToken,
        language: str,
    ) -> float:
        """Single capacity measurement path — always passes full style + language."""
        _assert_style_complete(style)
        return self._text.estimate_block_height_in(
            text,
            box_width_in=box_width_in,
            style=style,
            language=language,
        )

    def _caption_height_budget(
        self,
        slide: SlideSpec,
        design_system: DesignSystem,
        *,
        usable_width: float,
        language: str,
        needs_caption: bool,
    ) -> float:
        if not needs_caption:
            return 0.0
        caption_style = design_system.typography.caption
        _assert_style_complete(caption_style)
        sample = ""
        if slide.visual_requirements:
            sample = "；".join(
                req.description.strip()
                for req in slide.visual_requirements
                if getattr(req, "description", None)
            )[:120]
        if not sample.strip():
            sample = "图注：项目图纸示意"
        measured = self._measure_styled(
            sample,
            box_width_in=max(0.01, usable_width * 0.9),
            style=caption_style,
            language=language,
        )
        return max(_CAPTION_FLOOR_IN, measured)

    def _drawing_budgets(
        self,
        *,
        usable_width: float,
        usable_height: float,
        visual_intent: VisualIntent | None,
        layout_family: LayoutFamily | None,
    ) -> dict[str, float | bool]:
        content = (
            visual_intent.dominant_content_type if visual_intent is not None else None
        )
        needs_drawing = layout_family == LayoutFamily.DRAWING_FOCUS or content in {
            VisualContentType.SITE_PLAN,
            VisualContentType.FLOOR_PLAN,
            VisualContentType.SECTION,
            VisualContentType.ELEVATION,
        }
        needs_diagram_chrome = content == VisualContentType.ANALYTICAL_DIAGRAM or (
            layout_family == LayoutFamily.ANALYTICAL_DIAGRAM
        )
        needs_chrome = bool(needs_drawing or needs_diagram_chrome)

        min_h = 0.0
        legend_h = 0.0
        density = 0.0
        if needs_drawing:
            min_h = max(
                usable_height * _DRAWING_MIN_HEIGHT_FRACTION,
                usable_width * _DRAWING_MIN_WIDTH_FRACTION * 0.55,
            )
            legend_h = _LEGEND_STRIP_HEIGHT_IN
            density = _ANNOTATION_DENSITY_BY_CONTENT.get(
                content or VisualContentType.SITE_PLAN,
                0.6,
            )
        elif needs_diagram_chrome:
            min_h = usable_height * 0.35
            legend_h = _LEGEND_STRIP_HEIGHT_IN * 0.6
            density = _ANNOTATION_DENSITY_BY_CONTENT.get(
                VisualContentType.ANALYTICAL_DIAGRAM,
                0.55,
            )
        elif content in _PHOTO_CONTENT_TYPES:
            # Photos share area budget but not drawing chrome floors.
            density = _ANNOTATION_DENSITY_BY_CONTENT.get(content, 0.2)

        return {
            "needs_drawing_chrome": needs_chrome,
            "min_readable_height": min_h,
            "legend_height": legend_h,
            "annotation_density": density,
        }

    def _image_height_budget(
        self,
        slide: SlideSpec,
        *,
        usable_height: float,
        visual_intent: VisualIntent | None,
        layout_family: LayoutFamily | None,
        drawing_min_height: float,
    ) -> float:
        fraction = 0.0
        if layout_family is not None:
            fraction = max(fraction, _IMAGE_HEIGHT_FRACTIONS.get(layout_family, 0.0))
        if visual_intent is not None:
            content = visual_intent.dominant_content_type
            if content in _DRAWING_CONTENT_TYPES | _PHOTO_CONTENT_TYPES:
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
        return max(usable_height * fraction, drawing_min_height)

    def _annotation_height_budget(
        self,
        *,
        image_height: float,
        visual_intent: VisualIntent | None,
        layout_family: LayoutFamily | None,
        annotation_density: float,
        needs_drawing_chrome: bool,
    ) -> float:
        needs_annotation = image_height > 0 or needs_drawing_chrome
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
        if not needs_annotation:
            return 0.0
        density = max(0.15, annotation_density) if needs_drawing_chrome else max(
            0.1, annotation_density
        )
        return _ANNOTATION_BASE_STRIP_IN * (0.5 + density)


def detect_slide_language(slide: SlideSpec) -> str:
    """Return ``zh`` / ``en`` / ``mixed`` from slide copy for measurement bias."""
    blob = " ".join(
        [
            slide.title or "",
            slide.message or "",
            " ".join(slide.key_points or []),
        ]
    )
    if not blob.strip():
        return "zh"
    cjk = len(_CJK_RE.findall(blob))
    latin = sum(1 for ch in blob if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    if cjk and latin:
        return "mixed"
    if cjk:
        return "zh"
    if latin:
        return "en"
    return "zh"


def _assert_style_complete(style: TextStyleToken) -> None:
    if not style.font_family or style.font_size <= 0:
        raise ValueError("capacity text measure requires font_family and font_size")
    if style.font_weight < 100 or style.line_height <= 0:
        raise ValueError("capacity text measure requires font_weight and line_height")


def _recommend_action(
    capacity_ratio: float,
    status: CapacityStatus,
) -> CapacityRecommendedAction:
    if status == CapacityStatus.IMPOSSIBLE:
        return "blocked"
    if capacity_ratio > SPLIT_SLIDE_RATIO:
        return "split_slide"
    if status == CapacityStatus.OVERLOADED or capacity_ratio > ADAPT_CONTENT_RATIO:
        return "adapt_content"
    return "proceed"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
