"""LayoutFamily aliases and coercion (DOM-006).

``LayoutFamily`` is the controlled vocabulary for geometry selection.
Blank / unset is allowed; aliases normalize; unknown values are rejected.
"""

from __future__ import annotations

from archium.domain.visual.enums import LayoutFamily

# Human / legacy keys → canonical LayoutFamily values.
LAYOUT_FAMILY_ALIASES: dict[str, LayoutFamily] = {
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
    "title": LayoutFamily.HERO,
}


def coerce_layout_family(value: object) -> LayoutFamily | None:
    """Coerce raw input to LayoutFamily, or None when unset.

    Raises:
        ValueError: when a non-blank value is not a known family or alias.
    """
    if value is None:
        return None
    if isinstance(value, LayoutFamily):
        return value
    key = str(value).strip().casefold()
    if not key:
        return None
    if key in LAYOUT_FAMILY_ALIASES:
        return LAYOUT_FAMILY_ALIASES[key]
    try:
        return LayoutFamily(key)
    except ValueError as exc:
        allowed = ", ".join(sorted(member.value for member in LayoutFamily))
        raise ValueError(
            f"unknown layout_family {value!r}; expected one of: {allowed}"
        ) from exc


def layout_family_value(family: LayoutFamily | None) -> str:
    """Serialize for DTO / UI (empty string means unset)."""
    return family.value if family is not None else ""
