"""Human-facing labels and evidence hints for Visual Grammar archetypes."""

from __future__ import annotations

from archium.domain.visual.visual_grammar import (
    PageArchetype,
    coerce_page_archetype,
    get_recipe,
    get_visual_grammar_registry,
)

_AUTO_OPTION = "auto"
_GENERIC_OPTION = PageArchetype.GENERIC.value


def archetype_select_options() -> list[str]:
    """Selectbox values: auto + all registered archetypes."""
    return [_AUTO_OPTION, *[item.value for item in get_visual_grammar_registry()]]


def archetype_label(value: object | None) -> str:
    """Display name for a page archetype value (or auto/generic)."""
    if value is None or value == "" or value == _AUTO_OPTION:
        return "自动识别"
    archetype = coerce_page_archetype(value)
    if archetype is None:
        return str(value)
    return get_recipe(archetype).display_name


def format_archetype_option(value: str) -> str:
    if value == _AUTO_OPTION:
        return "自动识别"
    label = archetype_label(value)
    if value == _GENERIC_OPTION:
        return label
    return f"{label}（{value}）"


def coerce_archetype_selection(value: object | None) -> PageArchetype | None:
    """Map UI selection to domain archetype (None = auto-detect)."""
    if value is None or value == "" or value == _AUTO_OPTION:
        return None
    archetype = coerce_page_archetype(value)
    if archetype is None or archetype == PageArchetype.GENERIC:
        return PageArchetype.GENERIC if archetype == PageArchetype.GENERIC else None
    return archetype


def selection_value_for_intent(page_archetype: PageArchetype | None) -> str:
    if page_archetype is None:
        return _AUTO_OPTION
    return page_archetype.value


def grammar_evidence_hints(page_archetype: PageArchetype | None) -> list[str]:
    """Required evidence slot lines for an archetype (empty for auto/generic)."""
    if page_archetype is None or page_archetype == PageArchetype.GENERIC:
        return []
    recipe = get_recipe(page_archetype)
    return [
        f"[grammar:{slot.role}] {slot.description}"
        for slot in recipe.required_evidence_slots
        if slot.required
    ]


def merge_grammar_evidence(
    existing: list[str],
    page_archetype: PageArchetype | None,
) -> list[str]:
    """Keep user evidence; append missing grammar slot hint lines."""
    hints = grammar_evidence_hints(page_archetype)
    if not hints:
        return list(existing)
    merged = list(existing)
    for hint in hints:
        role_tag = hint.split("]", 1)[0] + "]"
        if any(role_tag in item for item in merged):
            continue
        # Also skip when the bare role name already appears.
        role = role_tag.removeprefix("[grammar:").removesuffix("]")
        if any(role in item.replace(" ", "") for item in merged):
            continue
        merged.append(hint)
    return merged
