"""Executable draw specs for VisualPrimitives — geometry + style + meaning.

Concept says *which* part; DrawSpec says *how it is drawn* (still relative,
absolute inches resolved by the materializer against a frame).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class GeometryType(StrEnum):
    SEGMENT = "segment"  # straight axis-aligned or diagonal bar
    POLYLINE = "polyline"  # connected segments
    BEZIER_APPROX = "bezier_approx"  # sampled quadratic → bars
    DISK = "disk"
    RECT_WASH = "rect_wash"
    RULE = "rule"  # thin horizontal rule


class PrimitiveStyleSpec(DomainModel):
    """Stroke/fill resolved via ColorStory role → named swatch → hex."""

    stroke_role: str = Field(default="accent", max_length=32)
    fill_role: str | None = Field(default=None, max_length=32)
    width_pt: float = Field(default=1.5, ge=0.35, le=8.0)
    opacity: float = Field(default=0.85, ge=0.05, le=1.0)
    dash: str = Field(default="solid", max_length=16)

    def as_dict(self) -> dict[str, object]:
        return {
            "stroke_role": self.stroke_role,
            "fill_role": self.fill_role,
            "width_pt": self.width_pt,
            "opacity": self.opacity,
            "dash": self.dash,
        }


class PrimitiveGeometrySpec(DomainModel):
    """Relative geometry inside a placement frame (0–1 coords)."""

    type: GeometryType = GeometryType.SEGMENT
    # Straight / rule endpoints (normalized).
    x0: float = Field(default=0.1, ge=0.0, le=1.0)
    y0: float = Field(default=0.5, ge=0.0, le=1.0)
    x1: float = Field(default=0.9, ge=0.0, le=1.0)
    y1: float = Field(default=0.5, ge=0.0, le=1.0)
    # Quadratic control for bezier_approx (normalized).
    cx: float = Field(default=0.5, ge=0.0, le=1.0)
    cy: float = Field(default=0.2, ge=0.0, le=1.0)
    curvature: float = Field(default=0.4, ge=0.0, le=1.0)
    samples: int = Field(default=6, ge=3, le=16)
    # Disk / wash size (normalized).
    radius: float = Field(default=0.04, ge=0.01, le=0.5)
    # Optional broken path: emit two segments with a gap (fragment rhetoric).
    broken: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "type": self.type.value,
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
            "cx": self.cx,
            "cy": self.cy,
            "curvature": self.curvature,
            "samples": self.samples,
            "radius": self.radius,
            "broken": self.broken,
        }


class PrimitiveDrawSpec(DomainModel):
    """Full executable recipe for one visual part."""

    geometry: PrimitiveGeometrySpec = Field(default_factory=PrimitiveGeometrySpec)
    style: PrimitiveStyleSpec = Field(default_factory=PrimitiveStyleSpec)
    meaning: str = Field(default="", max_length=120)
    # When true, materializer may emit a rhetoric pack (existing+conflict+network).
    rhetoric_pack: str | None = Field(default=None, max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "geometry": self.geometry.as_dict(),
            "style": self.style.as_dict(),
            "meaning": self.meaning,
            "rhetoric_pack": self.rhetoric_pack,
        }


# --- Catalog draw recipes (execution layer) ---

DRAW_FLOW_LINE = PrimitiveDrawSpec(
    geometry=PrimitiveGeometrySpec(
        type=GeometryType.BEZIER_APPROX,
        x0=0.08,
        y0=0.72,
        x1=0.92,
        y1=0.28,
        cx=0.55,
        cy=0.15,
        curvature=0.45,
        samples=7,
    ),
    style=PrimitiveStyleSpec(
        stroke_role="intervention",
        width_pt=2.0,
        opacity=0.88,
    ),
    meaning="circulation",
    rhetoric_pack="fragment_to_network",
)

DRAW_FLOW_LINE_EXISTING = PrimitiveDrawSpec(
    geometry=PrimitiveGeometrySpec(
        type=GeometryType.POLYLINE,
        x0=0.1,
        y0=0.35,
        x1=0.7,
        y1=0.75,
        cx=0.4,
        cy=0.55,
        broken=True,
        samples=4,
    ),
    style=PrimitiveStyleSpec(
        stroke_role="existing",
        width_pt=1.6,
        opacity=0.55,
        dash="solid",
    ),
    meaning="existing_circulation",
)

DRAW_AXIS_LINE = PrimitiveDrawSpec(
    geometry=PrimitiveGeometrySpec(
        type=GeometryType.SEGMENT,
        x0=0.32,
        y0=0.12,
        x1=0.32,
        y1=0.88,
    ),
    style=PrimitiveStyleSpec(
        stroke_role="neutral",
        width_pt=0.9,
        opacity=0.55,
    ),
    meaning="axis",
)

DRAW_THIN_RULE = PrimitiveDrawSpec(
    geometry=PrimitiveGeometrySpec(
        type=GeometryType.RULE,
        x0=0.0,
        y0=0.0,
        x1=1.0,
        y1=0.0,
    ),
    style=PrimitiveStyleSpec(
        stroke_role="neutral",
        width_pt=0.75,
        opacity=0.7,
    ),
    meaning="section_divider",
)

DRAW_NODE = PrimitiveDrawSpec(
    geometry=PrimitiveGeometrySpec(
        type=GeometryType.DISK,
        x0=0.48,
        y0=0.52,
        radius=0.035,
    ),
    style=PrimitiveStyleSpec(
        stroke_role="conflict",
        fill_role="conflict",
        width_pt=0.5,
        opacity=0.95,
    ),
    meaning="conflict_or_spatial_node",
)

DRAW_OVERLAY_MAP = PrimitiveDrawSpec(
    geometry=PrimitiveGeometrySpec(
        type=GeometryType.RECT_WASH,
        x0=0.05,
        y0=0.08,
        x1=0.95,
        y1=0.92,
    ),
    style=PrimitiveStyleSpec(
        stroke_role="intervention",
        fill_role="intervention",
        width_pt=0.5,
        opacity=0.12,
    ),
    meaning="analysis_layer",
)

DRAW_SPECS: dict[str, PrimitiveDrawSpec] = {
    "flow_line": DRAW_FLOW_LINE,
    "axis_line": DRAW_AXIS_LINE,
    "thin_rule": DRAW_THIN_RULE,
    "node": DRAW_NODE,
    "overlay_map": DRAW_OVERLAY_MAP,
}


def draw_spec_for(primitive_id: str) -> PrimitiveDrawSpec | None:
    return DRAW_SPECS.get(primitive_id)
