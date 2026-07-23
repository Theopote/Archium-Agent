"""Map SlideDesignBrief fields onto VisualIntent preferences."""

from __future__ import annotations

from archium.domain.slide_design_brief import SlideDesignBrief
from archium.domain.visual.enums import DensityLevel, LayoutFamily, VisualContentType
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry

_BRIEF_LAYOUT_ALIASES: dict[str, LayoutFamily] = {
    "hero": LayoutFamily.HERO,
    "evidence_board": LayoutFamily.EVIDENCE_BOARD,
    "photo_evidence_grid": LayoutFamily.EVIDENCE_BOARD,
    "evidence_grid": LayoutFamily.EVIDENCE_BOARD,
    "drawing_focus": LayoutFamily.DRAWING_FOCUS,
    "drawing": LayoutFamily.DRAWING_FOCUS,
    "site_plan": LayoutFamily.DRAWING_FOCUS,
    "floor_plan": LayoutFamily.DRAWING_FOCUS,
    "elevation": LayoutFamily.DRAWING_FOCUS,
    "section": LayoutFamily.DRAWING_FOCUS,
    "comparative_matrix": LayoutFamily.COMPARATIVE_MATRIX,
    "comparison": LayoutFamily.COMPARATIVE_MATRIX,
    "process_narrative": LayoutFamily.PROCESS_NARRATIVE,
    "analytical_diagram": LayoutFamily.ANALYTICAL_DIAGRAM,
    "metric_dashboard": LayoutFamily.METRIC_DASHBOARD,
    "metric": LayoutFamily.METRIC_DASHBOARD,
    "data": LayoutFamily.METRIC_DASHBOARD,
    "strategy_cards": LayoutFamily.STRATEGY_CARDS,
    "textual_argument": LayoutFamily.TEXTUAL_ARGUMENT,
    "textual": LayoutFamily.TEXTUAL_ARGUMENT,
    "hybrid_canvas": LayoutFamily.HYBRID_CANVAS,
    "content": LayoutFamily.PROCESS_NARRATIVE,
}

_BRIEF_DENSITY_MAP: dict[str, DensityLevel] = {
    "low": DensityLevel.SPACIOUS,
    "medium": DensityLevel.BALANCED,
    "high": DensityLevel.COMPACT,
    "spacious": DensityLevel.SPACIOUS,
    "balanced": DensityLevel.BALANCED,
    "compact": DensityLevel.COMPACT,
}

_BRIEF_VISUAL_TO_CONTENT: dict[str, VisualContentType] = {
    "drawing": VisualContentType.SITE_PLAN,
    "photo": VisualContentType.PHOTO_EVIDENCE,
    "metric": VisualContentType.METRICS,
    "title": VisualContentType.HERO_IMAGE,
    "comparison": VisualContentType.COMPARISON,
    "content": VisualContentType.TEXT_ARGUMENT,
}


def resolve_brief_layout_family(raw: str) -> LayoutFamily | None:
    key = (raw or "").strip().lower()
    if not key:
        return None
    if key in _BRIEF_LAYOUT_ALIASES:
        return _BRIEF_LAYOUT_ALIASES[key]
    try:
        return LayoutFamily(key)
    except ValueError:
        return None


def apply_design_brief_to_intent(
    intent: VisualIntent,
    brief: SlideDesignBrief,
) -> VisualIntent:
    """Override intent fields from an approved (or ready) design brief."""
    updates: dict[str, object] = {}

    family = resolve_brief_layout_family(brief.layout_family)
    if family is not None:
        implemented = {item.family for item in get_layout_family_registry().implemented()}
        if family in implemented:
            rest = [item for item in intent.preferred_layout_families if item != family]
            updates["preferred_layout_families"] = [family, *rest][:3]

    density = _BRIEF_DENSITY_MAP.get(brief.expected_density)
    if density is not None:
        updates["density_level"] = density

    content = _BRIEF_VISUAL_TO_CONTENT.get(brief.primary_visual_type.strip().lower())
    if content is not None:
        updates["dominant_content_type"] = content

    if brief.primary_asset_ids:
        updates["hero_asset_id"] = brief.primary_asset_ids[0]
        supporting = list(dict.fromkeys([*brief.primary_asset_ids[1:], *brief.supporting_asset_ids]))
        updates["supporting_asset_ids"] = supporting
    elif brief.supporting_asset_ids:
        updates["supporting_asset_ids"] = list(brief.supporting_asset_ids)

    if brief.drawing_policy is not None and brief.drawing_policy.forbid_cover_crop:
        updates["image_treatment"] = "drawing_contain"
    elif brief.image_policy is not None:
        updates["image_treatment"] = (
            "photo_cover" if brief.image_policy.fit_mode == "cover" else "photo_contain"
        )

    if brief.central_claim.strip():
        updates["audience_takeaway"] = brief.central_claim.strip()
    if brief.page_task.strip():
        updates["communication_goal"] = brief.page_task.strip()

    if not updates:
        return intent
    return intent.model_copy(update=updates)
