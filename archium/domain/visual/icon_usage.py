"""Apply IconUsagePolicy to icon refs and matcher results."""

from __future__ import annotations

from archium.domain.visual.architectural_icon import ArchitecturalIconMatch
from archium.domain.visual.enums import LayoutFamily, VisualContentType
from archium.domain.visual.icon_usage_policy import (
    IconUsagePolicy,
    default_icon_usage_policy,
)
from archium.domain.visual.slide_capacity_budget import (
    CapacityStatus,
    SlideCapacityBudget,
)


def icons_allowed_for_family(
    layout_family: LayoutFamily | str | None,
    *,
    policy: IconUsagePolicy | None = None,
    content_type: VisualContentType | str | None = None,
) -> bool:
    rules = policy or default_icon_usage_policy()
    family = (
        layout_family.value
        if isinstance(layout_family, LayoutFamily)
        else (layout_family or "")
    )
    if family in rules.forbidden_layout_families:
        return False
    if not rules.allow_on_drawing_pages:
        drawing_types = {
            VisualContentType.SITE_PLAN.value,
            VisualContentType.FLOOR_PLAN.value,
            VisualContentType.SECTION.value,
            VisualContentType.ELEVATION.value,
            "drawing",
            "drawing_focus",
        }
        kind = (
            content_type.value
            if isinstance(content_type, VisualContentType)
            else (content_type or "")
        )
        if kind in drawing_types or family == LayoutFamily.DRAWING_FOCUS.value:
            return False
    if rules.allowed_layout_families and family:
        return family in rules.allowed_layout_families
    return True


def max_icons_for_family(
    layout_family: LayoutFamily | str | None,
    *,
    policy: IconUsagePolicy | None = None,
) -> int:
    rules = policy or default_icon_usage_policy()
    family = (
        layout_family.value
        if isinstance(layout_family, LayoutFamily)
        else (layout_family or "")
    )
    if family == LayoutFamily.METRIC_DASHBOARD.value:
        return min(rules.max_icons_per_page, rules.max_icons_metric_dashboard)
    if family == LayoutFamily.PROCESS_NARRATIVE.value:
        return min(rules.max_icons_per_page, rules.max_icons_process_narrative)
    return rules.max_icons_per_page


def filter_icon_refs(
    icon_refs: list[str],
    *,
    layout_family: LayoutFamily | str | None = None,
    content_type: VisualContentType | str | None = None,
    capacity: SlideCapacityBudget | None = None,
    expected_density: str | None = None,
    policy: IconUsagePolicy | None = None,
) -> list[str]:
    """Clamp / drop icon refs according to usage policy."""
    rules = policy or default_icon_usage_policy()
    if not icons_allowed_for_family(
        layout_family, policy=rules, content_type=content_type
    ):
        return []
    if (
        rules.remove_when_capacity_overloaded
        and capacity is not None
        and capacity.status in {CapacityStatus.OVERLOADED, CapacityStatus.IMPOSSIBLE}
    ):
        return []
    if rules.remove_when_density_high and (expected_density or "").lower() == "high":
        return []
    limit = max_icons_for_family(layout_family, policy=rules)
    return list(icon_refs[:limit])


def accept_match(
    match: ArchitecturalIconMatch | None,
    *,
    policy: IconUsagePolicy | None = None,
    allow_decorative: bool | None = None,
) -> ArchitecturalIconMatch | None:
    rules = policy or default_icon_usage_policy()
    if match is None:
        return None
    if match.score < rules.min_match_confidence and match.matched_by == "embedding":
        return None
    # Exact/alias/category can be slightly below min for embeddings only;
    # still enforce a floor for weak embedding hits.
    if match.matched_by == "embedding" and match.score < rules.min_match_confidence:
        return None
    decorative_ok = (
        rules.allow_decorative if allow_decorative is None else allow_decorative
    )
    if not decorative_ok:
        blob = " ".join(
            [
                match.icon.id,
                match.icon.canonical_name,
                match.icon.description,
                *match.icon.categories,
            ]
        ).lower()
        if any(token in blob for token in ("decor", "ornament", "sticker", "emoji")):
            return None
    return match
