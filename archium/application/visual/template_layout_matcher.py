"""Rank ArchitecturalTemplate pages for a SlideSpec / VisualIntent."""

from __future__ import annotations

from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplatePageType,
)
from archium.domain.visual.enums import DensityLevel, LayoutFamily, VisualContentType
from archium.domain.visual.template_match import TemplateLayoutCandidate
from archium.domain.visual.visual_intent import VisualIntent

_CONTENT_TYPE_TO_PAGE: dict[VisualContentType, set[TemplatePageType]] = {
    VisualContentType.SITE_PLAN: {TemplatePageType.DRAWING_FOCUS},
    VisualContentType.FLOOR_PLAN: {TemplatePageType.DRAWING_FOCUS},
    VisualContentType.SECTION: {TemplatePageType.DRAWING_FOCUS},
    VisualContentType.ELEVATION: {TemplatePageType.DRAWING_FOCUS},
    VisualContentType.ANALYTICAL_DIAGRAM: {
        TemplatePageType.DRAWING_FOCUS,
        TemplatePageType.PROCESS,
    },
    VisualContentType.HERO_IMAGE: {TemplatePageType.COVER, TemplatePageType.SECTION},
    VisualContentType.PHOTO_EVIDENCE: {
        TemplatePageType.PHOTO_GRID,
        TemplatePageType.CASE_COMPARISON,
    },
    VisualContentType.COMPARISON: {
        TemplatePageType.CASE_COMPARISON,
        TemplatePageType.BEFORE_AFTER,
    },
    VisualContentType.METRICS: {TemplatePageType.METRIC},
    VisualContentType.PROCESS: {TemplatePageType.PROCESS, TemplatePageType.TIMELINE},
    VisualContentType.TEXT_ARGUMENT: {
        TemplatePageType.TEXT_ARGUMENT,
        TemplatePageType.AGENDA,
    },
    VisualContentType.MIXED: {
        TemplatePageType.TEXT_ARGUMENT,
        TemplatePageType.CASE_COMPARISON,
        TemplatePageType.PHOTO_GRID,
    },
}

_FAMILY_TO_PAGE: dict[LayoutFamily, set[TemplatePageType]] = {
    LayoutFamily.HERO: {TemplatePageType.COVER, TemplatePageType.SECTION, TemplatePageType.CLOSING},
    LayoutFamily.DRAWING_FOCUS: {TemplatePageType.DRAWING_FOCUS},
    LayoutFamily.EVIDENCE_BOARD: {TemplatePageType.PHOTO_GRID},
    LayoutFamily.COMPARATIVE_MATRIX: {
        TemplatePageType.CASE_COMPARISON,
        TemplatePageType.BEFORE_AFTER,
    },
    LayoutFamily.METRIC_DASHBOARD: {TemplatePageType.METRIC},
    LayoutFamily.PROCESS_NARRATIVE: {TemplatePageType.PROCESS, TemplatePageType.TIMELINE},
    LayoutFamily.TEXTUAL_ARGUMENT: {
        TemplatePageType.TEXT_ARGUMENT,
        TemplatePageType.AGENDA,
    },
    LayoutFamily.ANALYTICAL_DIAGRAM: {TemplatePageType.DRAWING_FOCUS, TemplatePageType.PROCESS},
    LayoutFamily.STRATEGY_CARDS: {TemplatePageType.TEXT_ARGUMENT},
    LayoutFamily.HYBRID_CANVAS: {TemplatePageType.CASE_COMPARISON, TemplatePageType.PHOTO_GRID},
}

_DENSITY_TARGETS: dict[DensityLevel, float] = {
    DensityLevel.SPACIOUS: 0.30,
    DensityLevel.BALANCED: 0.45,
    DensityLevel.COMPACT: 0.60,
}


class TemplateLayoutMatcher:
    """Rule-based ranking of template layouts for architectural slides."""

    def rank_layouts(
        self,
        *,
        slide_spec: SlideSpec,
        visual_intent: VisualIntent,
        assets: list[Asset],
        template: ArchitecturalTemplate,
        limit: int = 3,
    ) -> list[TemplateLayoutCandidate]:
        if template.layouts and not any(layout.slots for layout in template.layouts):
            return []

        scored: list[TemplateLayoutCandidate] = []
        for layout in template.layouts:
            if not layout.slots:
                continue
            score, reasons = self._score_layout(
                layout=layout,
                slide_spec=slide_spec,
                visual_intent=visual_intent,
                assets=assets,
            )
            scored.append(
                TemplateLayoutCandidate(
                    template_id=template.id,
                    template_name=template.name,
                    layout_id=layout.id,
                    layout_name=layout.name,
                    page_index=layout.page_index,
                    page_type=layout.page_type.value,
                    score=round(score, 3),
                    reasons=reasons,
                    design_system_id=template.design_system_id,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[: max(1, limit)] if scored else []

    def _score_layout(
        self,
        *,
        layout: ArchitecturalTemplateLayout,
        slide_spec: SlideSpec,
        visual_intent: VisualIntent,
        assets: list[Asset],
    ) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []

        preferred_pages = _CONTENT_TYPE_TO_PAGE.get(visual_intent.dominant_content_type, set())
        if layout.page_type in preferred_pages:
            score += 3.0
            reasons.append(f"page_type matches {visual_intent.dominant_content_type.value}")
        elif layout.page_type == TemplatePageType.UNKNOWN:
            score += 0.2
            reasons.append("page_type unknown (weak match)")
        else:
            score -= 0.5
            reasons.append(f"page_type {layout.page_type.value} differs from intent")

        for family in visual_intent.preferred_layout_families:
            if layout.page_type in _FAMILY_TO_PAGE.get(family, set()):
                score += 1.5
                reasons.append(f"preferred family {family.value}")
                break

        drawing_assets = [asset for asset in assets if asset.asset_type == AssetType.DRAWING]
        photo_assets = [asset for asset in assets if asset.asset_type == AssetType.PHOTO]
        asset_count = len(assets)
        if visual_intent.hero_asset_id is not None:
            asset_count = max(asset_count, 1 + len(visual_intent.supporting_asset_ids))

        if layout.supports_drawing and drawing_assets:
            score += 2.0
            reasons.append("drawing support + drawing assets")
        elif layout.supports_drawing and visual_intent.dominant_content_type in {
            VisualContentType.SITE_PLAN,
            VisualContentType.FLOOR_PLAN,
            VisualContentType.SECTION,
            VisualContentType.ELEVATION,
        }:
            score += 1.5
            reasons.append("drawing support for drawing intent")
        elif layout.supports_drawing and not drawing_assets:
            score -= 0.8
            reasons.append("drawing layout without drawing assets")

        if layout.supports_photo and photo_assets:
            score += 1.2
            reasons.append("photo support + photo assets")
        if layout.supports_metrics and visual_intent.dominant_content_type == VisualContentType.METRICS:
            score += 1.5
            reasons.append("metrics support")
        if layout.supports_before_after and visual_intent.dominant_content_type == VisualContentType.COMPARISON:
            score += 1.5
            reasons.append("before/after support")
        if layout.supports_case_reference and "案例" in (slide_spec.title + slide_spec.message):
            score += 0.8
            reasons.append("case reference cue")

        if asset_count < layout.minimum_asset_count:
            score -= 1.5
            reasons.append("asset count below template minimum")
        elif asset_count > layout.maximum_asset_count:
            score -= 0.6
            reasons.append("asset count above template maximum")
        else:
            score += 0.8
            reasons.append("asset count within template range")

        text_len = len(slide_spec.title) + len(slide_spec.message) + sum(len(p) for p in slide_spec.key_points)
        if text_len < layout.minimum_text_length:
            score -= 0.5
            reasons.append("text shorter than template minimum")
        elif text_len > layout.maximum_text_length:
            score -= 0.4
            reasons.append("text longer than template maximum")
        else:
            score += 0.5
            reasons.append("text length within template range")

        density_target = _DENSITY_TARGETS.get(visual_intent.density_level, 0.45)
        low, high = layout.density_range
        mid = (low + high) / 2.0
        density_gap = abs(mid - density_target)
        score += max(0.0, 1.0 - density_gap * 2.0)
        if density_gap < 0.15:
            reasons.append("density aligns with intent")

        # Prefer pages with annotated slots.
        score += min(1.0, len(layout.slots) / 8.0)
        return max(0.0, score), reasons
