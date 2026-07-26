"""Map VisualLanguage primitives → bundled architectural icon refs (SVG)."""

from __future__ import annotations

# Prefer existing curated pack over inventing emoji glyphs.
PRIMITIVE_TO_ICON_REF: dict[str, str] = {
    "circulation": "icon:pedestrian_flow",
    "flow_line": "icon:pedestrian_flow",
    "entrance": "icon:emergency_access",
    "green_buffer": "icon:healing_garden",
    "node": "icon:accessibility",  # light mark; not a car emoji
    "overlay_map": "icon:smart_systems",
    "transition_arrow": "icon:public_transport",
}


def icon_ref_for_primitive(primitive_id: str) -> str | None:
    return PRIMITIVE_TO_ICON_REF.get(primitive_id)
