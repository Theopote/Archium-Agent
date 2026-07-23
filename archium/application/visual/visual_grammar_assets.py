"""Bridge Visual Grammar evidence slots ↔ asset bindings / hero selection."""

from __future__ import annotations

import re
from uuid import UUID

from archium.domain.enums import SlideAssetBindingRole, VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual.visual_grammar import PageArchetype

_GRAMMAR_ROLE_RE = re.compile(r"\[grammar:([a-z0-9_]+)\]", re.I)

# Binding role → grammar evidence roles it may satisfy (first match preferred).
BINDING_ROLE_TO_GRAMMAR_SLOTS: dict[SlideAssetBindingRole, tuple[str, ...]] = {
    SlideAssetBindingRole.PROJECT_PHOTO: (
        "historic_or_context_photo",
        "site_photos",
        "problem_tension",
        "before",
        "after",
    ),
    SlideAssetBindingRole.SUPPORTING_PHOTO: (
        "problem_tension",
        "site_photos",
        "after",
        "before",
        "historic_or_context_photo",
    ),
    SlideAssetBindingRole.PRIMARY_DRAWING: (
        "map_hero",
        "concept_diagram",
        "site_photos",
    ),
    SlideAssetBindingRole.REFERENCE_CASE: (
        "concept_diagram",
        "historic_or_context_photo",
    ),
    SlideAssetBindingRole.BACKGROUND: ("historic_or_context_photo",),
    SlideAssetBindingRole.METRIC_SOURCE: (),
    SlideAssetBindingRole.LOGO: (),
}

# Archetype → preferred grammar roles for the layout hero visual.
HERO_GRAMMAR_ROLES: dict[PageArchetype, tuple[str, ...]] = {
    PageArchetype.NARRATIVE_OPENING: ("historic_or_context_photo",),
    PageArchetype.SITE_CONTEXT_ANALYSIS: ("map_hero",),
    PageArchetype.SITE_PROBLEM_DIAGNOSIS: ("site_photos",),
    PageArchetype.DESIGN_STRATEGY: ("concept_diagram",),
    PageArchetype.BEFORE_AFTER_TRANSFORMATION: ("before", "after"),
}

_HISTORIC_HINTS = frozenset(
    {"historic", "history", "历史", "沿革", "既往", "语境", "context", "开篇"}
)


def visual_types_compatible(left: VisualType, right: VisualType) -> bool:
    """Loose type compatibility for binding onto grammar slots."""
    if left == right:
        return True
    families = (
        frozenset({VisualType.MAP, VisualType.SITE_PLAN, VisualType.FLOOR_PLAN}),
        frozenset({VisualType.SITE_PHOTO, VisualType.RENDERING, VisualType.COMPARISON}),
        frozenset({VisualType.DIAGRAM, VisualType.SITE_PLAN}),
    )
    return any(left in family and right in family for family in families)


def grammar_role_from_requirement(requirement: VisualRequirement) -> str | None:
    """Extract ``[grammar:role]`` from a visual requirement description."""
    match = _GRAMMAR_ROLE_RE.search(requirement.description or "")
    if match is None:
        return None
    return match.group(1).casefold()


def format_grammar_requirement_description(role: str, description: str) -> str:
    """Stable description prefix used by slot stamping and binding."""
    clean = description.strip() or role
    return f"[grammar:{role}] {clean}"


def preferred_grammar_slots_for_binding(
    binding_role: SlideAssetBindingRole,
) -> tuple[str, ...]:
    return BINDING_ROLE_TO_GRAMMAR_SLOTS.get(binding_role, ())


def find_requirement_for_grammar_slot(
    slide: SlideSpec,
    role: str,
) -> VisualRequirement | None:
    needle = role.casefold()
    for req in slide.visual_requirements:
        if grammar_role_from_requirement(req) == needle:
            return req
    return None


def resolve_grammar_hero_asset_id(slide: SlideSpec) -> UUID | None:
    """Pick hero asset from grammar-tagged requirements when available."""
    archetype = slide.page_archetype
    preferred_roles = HERO_GRAMMAR_ROLES.get(archetype, ()) if archetype else ()

    for role in preferred_roles:
        req = find_requirement_for_grammar_slot(slide, role)
        if req is not None and req.primary_asset_id is not None:
            return req.primary_asset_id

    for req in slide.visual_requirements:
        if req.type == VisualType.TEXT_ONLY:
            continue
        if grammar_role_from_requirement(req) is None:
            continue
        if req.primary_asset_id is not None:
            return req.primary_asset_id
    return None


def grammar_asset_match_bonus(
    requirement: VisualRequirement,
    *,
    asset_search_text: str,
) -> float:
    """Small ranking boost when asset text aligns with a grammar slot role."""
    role = grammar_role_from_requirement(requirement)
    if role is None:
        return 0.0
    blob = asset_search_text.casefold()
    if role == "historic_or_context_photo":
        if any(hint in blob for hint in _HISTORIC_HINTS):
            return 0.18
    if role in {"site_photos", "problem_tension"}:
        if any(token in blob for token in ("现场", "现状", "问题", "site", "problem")):
            return 0.12
    if role == "map_hero":
        if any(token in blob for token in ("区位", "地图", "map", "交通", "site_plan")):
            return 0.15
    if role == "concept_diagram":
        if any(token in blob for token in ("概念", "策略", "diagram", "concept")):
            return 0.12
    return 0.0
