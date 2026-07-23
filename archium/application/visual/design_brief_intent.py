"""Map SlideDesignBrief fields onto VisualIntent preferences."""

from __future__ import annotations

from archium.application.visual.visual_grammar_intent import apply_grammar_to_intent
from archium.domain.slide_design_brief import SlideDesignBrief
from archium.domain.visual.enums import DensityLevel, LayoutFamily, VisualContentType
from archium.domain.visual.layout_family_normalize import coerce_layout_family
from archium.domain.visual.visual_grammar import PageArchetype
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry

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


def resolve_brief_layout_family(raw: LayoutFamily | str | None) -> LayoutFamily | None:
    """Resolve brief layout preference; blank → None. Illegal strings raise."""
    if isinstance(raw, LayoutFamily):
        return raw
    return coerce_layout_family(raw)


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
        supporting = list(
            dict.fromkeys([*brief.primary_asset_ids[1:], *brief.supporting_asset_ids])
        )
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

    result = intent.model_copy(update=updates) if updates else intent
    if brief.page_archetype is not None and brief.page_archetype != PageArchetype.GENERIC:
        result = apply_grammar_to_intent(
            result,
            page_archetype=brief.page_archetype,
        )
    return result
