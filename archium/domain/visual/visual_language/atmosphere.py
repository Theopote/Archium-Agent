"""Background atmosphere — CAD grid / contour / blueprint (architectural, not stock texture)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class AtmosphereKind(StrEnum):
    NONE = "none"
    CAD_GRID = "cad_grid"
    CONTOUR = "contour"
    BLUEPRINT = "blueprint"
    DOT_FIELD = "dot_field"


class AtmosphereSpec(DomainModel):
    """Page background atmosphere recipe (Visual Rhetoric Layer)."""

    kind: AtmosphereKind = AtmosphereKind.NONE
    opacity: float = Field(default=0.12, ge=0.02, le=0.4)
    # How many grid lines / contour rings to emit (budgeted further by VisualBudget).
    density: int = Field(default=6, ge=2, le=16)
    stroke_swatch: str = Field(default="axis_line", max_length=40)
    source: str = Field(default="rules", max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "opacity": self.opacity,
            "density": self.density,
            "stroke_swatch": self.stroke_swatch,
            "source": self.source,
        }


def atmosphere_for_context(
    *,
    formula_id: str | None = None,
    metaphor: str | None = None,
    emotion: str | None = None,
) -> AtmosphereSpec:
    """Pick a restrained atmosphere from page grammar / metaphor."""
    formula_id = (formula_id or "").strip()
    metaphor = (metaphor or "").strip()
    emotion = (emotion or "").strip().lower()

    if formula_id in {"layer_analysis", "drawing_dominant"} or metaphor == "layered_site":
        return AtmosphereSpec(
            kind=AtmosphereKind.CAD_GRID,
            opacity=0.1,
            density=7,
            source="atmosphere:layer_or_drawing",
        )
    if formula_id in {"path_experience"} or metaphor in {
        "fragment_to_network",
        "path_to_experience",
    }:
        return AtmosphereSpec(
            kind=AtmosphereKind.CONTOUR,
            opacity=0.14,
            density=4,
            stroke_swatch="alert_red" if metaphor == "fragment_to_network" else "axis_line",
            source="atmosphere:path",
        )
    if formula_id in {"core_expansion", "monument_image"} or metaphor == "core_to_expansion":
        return AtmosphereSpec(
            kind=AtmosphereKind.DOT_FIELD,
            opacity=0.1,
            density=5,
            source="atmosphere:core",
        )
    if formula_id == "decision_metric" or emotion == "decision":
        return AtmosphereSpec(
            kind=AtmosphereKind.BLUEPRINT,
            opacity=0.08,
            density=5,
            source="atmosphere:decision",
        )
    if formula_id == "hero_statement" or emotion == "climax":
        return AtmosphereSpec(kind=AtmosphereKind.NONE, source="atmosphere:hero_clear")
    return AtmosphereSpec(kind=AtmosphereKind.NONE, source="atmosphere:default")
