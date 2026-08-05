"""GraphicMotif — project-level visual vocabulary (VQ-003).

Decorations grow from a motif (axis, flow nodes, contour…) rather than
random lines. Motif seeds primitive_ids / atmosphere / stroke cues consumed
by VisualLanguage apply + Primitive materializer.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class MotifType(StrEnum):
    AXIS_GRID = "axis_grid"
    FLOW_NODES = "flow_nodes"
    CONTOUR = "contour"
    SECTION_CUT = "section_cut"
    BEFORE_AFTER_SLICE = "before_after_slice"
    MODULE_INDEX = "module_index"
    PATH_SEQUENCE = "path_sequence"
    QUIET_RULE = "quiet_rule"


class StrokeStyle(DomainModel):
    color_token: str = Field(default="primary", min_length=1)
    width_pt: float = Field(default=0.75, ge=0.25, le=4.0)
    dash: str = Field(default="solid", pattern="^(solid|dash|dot)$")
    opacity: float = Field(default=0.7, ge=0.15, le=1.0)


class MarkerStyle(DomainModel):
    shape: str = Field(default="circle", pattern="^(circle|cross|square|none)$")
    size_pt: float = Field(default=8.0, ge=4.0, le=24.0)
    fill_token: str | None = Field(default="accent")
    stroke_token: str = Field(default="primary")


class GraphicMotif(DomainModel):
    """Project / page motif — executable cues, not free decoration."""

    motif_id: str = Field(min_length=1, max_length=64)
    motif_type: MotifType = MotifType.QUIET_RULE
    usage_rules: list[str] = Field(default_factory=list, max_length=8)
    stroke: StrokeStyle = Field(default_factory=StrokeStyle)
    marker: MarkerStyle = Field(default_factory=MarkerStyle)
    shape_vocabulary: list[str] = Field(
        default_factory=list,
        max_length=12,
        description="VisualPrimitive ids preferred by this motif.",
    )
    corner_language: str = Field(default="sharp", max_length=24)
    repetition_rule: str = Field(
        default="sparse",
        description="sparse | measured | dense — caps motif geometry count.",
    )
    color_role_bias: str = Field(
        default="intervention",
        description="ColorStory role preferred for motif strokes.",
    )
    max_marks: int = Field(default=4, ge=0, le=12)
    source: str = Field(default="rules", max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "motif_id": self.motif_id,
            "motif_type": self.motif_type.value,
            "usage_rules": list(self.usage_rules),
            "stroke": self.stroke.model_dump(),
            "marker": self.marker.model_dump(),
            "shape_vocabulary": list(self.shape_vocabulary),
            "corner_language": self.corner_language,
            "repetition_rule": self.repetition_rule,
            "color_role_bias": self.color_role_bias,
            "max_marks": self.max_marks,
            "source": self.source,
        }
