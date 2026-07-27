"""VisualNarrative — full visual strategy behind a VisualConcept (rhetoric, not layout).

Answers “how should this metaphor *behave* graphically?” — geometry motion,
semantic color roles, and which primitives to call.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class MotionDirection(StrEnum):
    """Visual motion implied by the metaphor (not animation)."""

    CONVERGING = "converging"
    EXPANDING = "expanding"
    SEQUENTIAL = "sequential"
    LAYERED = "layered"
    STATIC = "static"


class GraphicLayerMode(StrEnum):
    BEFORE_AFTER = "before_after"
    OVERLAY = "overlay"
    SINGLE = "single"
    SEQUENCE = "sequence"


class GraphicBehavior(DomainModel):
    """How geometry narrates the metaphor."""

    geometry: str = Field(
        min_length=1,
        max_length=80,
        description="e.g. broken_lines_to_curve, core_to_expansion",
    )
    direction: MotionDirection = MotionDirection.STATIC
    layer: GraphicLayerMode = GraphicLayerMode.SINGLE

    def as_dict(self) -> dict[str, object]:
        return {
            "geometry": self.geometry,
            "direction": self.direction.value,
            "layer": self.layer.value,
        }


class VisualNarrative(DomainModel):
    """Executable visual strategy for one concept (Visual Rhetoric Engine)."""

    name: str = Field(min_length=1, max_length=64)
    metaphor: str = Field(
        min_length=1,
        max_length=160,
        description="Human-readable metaphor sentence.",
    )
    graphic_language: GraphicBehavior = Field(
        default_factory=lambda: GraphicBehavior(geometry="static")
    )
    # Semantic roles → swatch ids (aligned with ColorStory / VisualConcept.color_story).
    color_roles: dict[str, str] = Field(default_factory=dict)
    recommended_components: list[str] = Field(
        default_factory=list,
        max_length=12,
        description="VisualPrimitive ids to prefer on this page.",
    )
    source: str = Field(default="rules", max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "metaphor": self.metaphor,
            "graphic_language": self.graphic_language.as_dict(),
            "color_story": dict(self.color_roles),
            "recommended_components": list(self.recommended_components),
            "source": self.source,
        }
