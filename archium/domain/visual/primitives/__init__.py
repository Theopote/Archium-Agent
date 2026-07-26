"""Visual primitives — architectural Figma-like parts (not emoji icon packs)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class PrimitiveKind(StrEnum):
    TYPOGRAPHY = "typography"
    LINE = "line"
    SHAPE = "shape"
    SYMBOL = "symbol"
    DIAGRAM = "diagram"
    ANNOTATION = "annotation"
    DECORATION = "decoration"
    IMAGE_MASK = "image_mask"


class VisualPrimitive(DomainModel):
    """One callable visual part — meaning + behavior, no absolute coordinates."""

    id: str = Field(min_length=1, max_length=64)
    kind: PrimitiveKind
    meaning: str = Field(default="", max_length=120)
    behavior: dict[str, object] = Field(default_factory=dict)
    glyph: str | None = Field(default=None, max_length=16)

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "meaning": self.meaning,
            "behavior": dict(self.behavior),
            "glyph": self.glyph,
        }


# --- Catalog (extend carefully; quality over quantity) ---

HERO_STATEMENT = VisualPrimitive(
    id="hero_statement",
    kind=PrimitiveKind.TYPOGRAPHY,
    meaning="edge_statement",
    behavior={"size": "huge", "position": "edge", "opacity": 0.9, "bilingual": True},
)

AXIS_LINE = VisualPrimitive(
    id="axis_line",
    kind=PrimitiveKind.LINE,
    meaning="circulation",
    behavior={"weight": 0.5, "dash": "solid", "orientation": "vertical"},
)

FLOW_LINE = VisualPrimitive(
    id="flow_line",
    kind=PrimitiveKind.LINE,
    meaning="circulation_flow",
    behavior={"weight": 1.0, "dash": "solid", "direction": "path"},
    glyph="→ → →",
)

THIN_RULE = VisualPrimitive(
    id="thin_rule",
    kind=PrimitiveKind.LINE,
    meaning="section_divider",
    behavior={"weight": 0.35, "dash": "solid", "orientation": "horizontal"},
)

NODE_MARK = VisualPrimitive(
    id="node",
    kind=PrimitiveKind.SYMBOL,
    meaning="spatial_node",
    behavior={"weight": "light"},
    glyph="●",
)

TRANSITION_ARROW = VisualPrimitive(
    id="transition_arrow",
    kind=PrimitiveKind.DIAGRAM,
    meaning="before_to_after",
    behavior={"weight": 1.0},
    glyph="→",
)

OVERLAY_MAP = VisualPrimitive(
    id="overlay_map",
    kind=PrimitiveKind.DIAGRAM,
    meaning="analysis_layer",
    behavior={"opacity": 0.55, "layer": "overlay"},
)

SECTION_INDEX = VisualPrimitive(
    id="section_index",
    kind=PrimitiveKind.ANNOTATION,
    meaning="chapter_marker",
    behavior={"tracking": "wide", "case": "uppercase"},
)

CIRCULATION_SYMBOL = VisualPrimitive(
    id="circulation",
    kind=PrimitiveKind.SYMBOL,
    meaning="pedestrian_or_service_flow",
    behavior={"style": "linear"},
    glyph="→ → →",
)

ENTRANCE_SYMBOL = VisualPrimitive(
    id="entrance",
    kind=PrimitiveKind.SYMBOL,
    meaning="threshold",
    behavior={"style": "linear"},
    glyph="▷",
)

GREEN_BUFFER = VisualPrimitive(
    id="green_buffer",
    kind=PrimitiveKind.SYMBOL,
    meaning="landscape_network",
    behavior={"style": "linear"},
    glyph="⑂",
)

_PRIMITIVES: dict[str, VisualPrimitive] = {
    p.id: p
    for p in (
        HERO_STATEMENT,
        AXIS_LINE,
        FLOW_LINE,
        THIN_RULE,
        NODE_MARK,
        TRANSITION_ARROW,
        OVERLAY_MAP,
        SECTION_INDEX,
        CIRCULATION_SYMBOL,
        ENTRANCE_SYMBOL,
        GREEN_BUFFER,
    )
}


def get_primitive(primitive_id: str) -> VisualPrimitive | None:
    return _PRIMITIVES.get(primitive_id)


def list_primitives() -> list[VisualPrimitive]:
    return list(_PRIMITIVES.values())


def resolve_primitives(ids: list[str]) -> list[VisualPrimitive]:
    """Preserve order; skip unknown ids."""
    out: list[VisualPrimitive] = []
    seen: set[str] = set()
    for item in ids:
        if item in seen:
            continue
        prim = _PRIMITIVES.get(item)
        if prim is None:
            continue
        seen.add(item)
        out.append(prim)
    return out
