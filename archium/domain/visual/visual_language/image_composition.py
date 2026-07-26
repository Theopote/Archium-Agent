"""ImageCompositionPlan — hero / detail / analysis lines (architectural photo rhetoric).

Not PhotoTreatment filters. Describes *how images speak on the page*:
primary frame + optional inset + overlaid analysis geometry.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class ImageCompositionMode(StrEnum):
    NONE = "none"
    HERO_ONLY = "hero_only"
    HERO_PLUS_DETAIL = "hero_plus_detail"
    BEFORE_AFTER = "before_after"
    PHOTO_PLUS_ANALYSIS = "photo_plus_analysis"
    LAYERED_BASE = "layered_base"


class ImageSlotRole(StrEnum):
    HERO = "hero"
    DETAIL = "detail"
    BEFORE = "before"
    AFTER = "after"
    BASE_MAP = "base_map"


class AnalysisLineKind(StrEnum):
    AXIS = "axis"
    FLOW = "flow"
    CONFLICT = "conflict"
    CUT = "cut"
    BOUNDARY = "boundary"


class ImageSlotSpec(DomainModel):
    """One image role in the composition (maps to LayoutElement roles)."""

    role: ImageSlotRole
    target_element_roles: list[str] = Field(default_factory=list, max_length=4)
    # Relative visual weight within the image stack (not absolute inches).
    weight: float = Field(default=1.0, ge=0.1, le=1.0)
    crop_hint: str = Field(default="full", max_length=32)

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "target_element_roles": list(self.target_element_roles),
            "weight": self.weight,
            "crop_hint": self.crop_hint,
        }


class AnalysisLineSpec(DomainModel):
    """Overlay line in normalized hero-frame coords (0–1)."""

    kind: AnalysisLineKind
    stroke_swatch: str = Field(default="axis_line", max_length=40)
    x0: float = Field(default=0.1, ge=0.0, le=1.0)
    y0: float = Field(default=0.5, ge=0.0, le=1.0)
    x1: float = Field(default=0.9, ge=0.0, le=1.0)
    y1: float = Field(default=0.5, ge=0.0, le=1.0)
    weight_pt: float = Field(default=1.25, ge=0.35, le=4.0)
    opacity: float = Field(default=0.85, ge=0.2, le=1.0)
    label: str | None = Field(default=None, max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "stroke_swatch": self.stroke_swatch,
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
            "weight_pt": self.weight_pt,
            "opacity": self.opacity,
            "label": self.label,
        }


class ImageCompositionPlan(DomainModel):
    """Page-level image rhetoric: main frame + optional detail + analysis geometry."""

    mode: ImageCompositionMode = ImageCompositionMode.NONE
    slots: list[ImageSlotSpec] = Field(default_factory=list, max_length=6)
    analysis_lines: list[AnalysisLineSpec] = Field(default_factory=list, max_length=8)
    max_details: int = Field(default=1, ge=0, le=3)
    source: str = Field(default="rules", max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "slots": [s.as_dict() for s in self.slots],
            "analysis_lines": [line.as_dict() for line in self.analysis_lines],
            "max_details": self.max_details,
            "source": self.source,
        }


def image_composition_for_context(
    *,
    formula_id: str | None = None,
    metaphor: str | None = None,
    emotion: str | None = None,
) -> ImageCompositionPlan:
    """Pick an image composition recipe from page grammar / metaphor."""
    formula_id = (formula_id or "").strip()
    metaphor = (metaphor or "").strip()
    emotion = (emotion or "").strip().lower()

    if formula_id in {"quiet_argument", "decision_metric", "section_opener", "quote_citation"} or emotion == "decision":
        return ImageCompositionPlan(
            mode=ImageCompositionMode.NONE,
            source="icp:text_led",
        )

    if formula_id in {"before_after_cut"} or metaphor == "existing_to_transformation":
        return ImageCompositionPlan(
            mode=ImageCompositionMode.BEFORE_AFTER,
            slots=[
                ImageSlotSpec(
                    role=ImageSlotRole.BEFORE,
                    target_element_roles=["hero_visual", "supporting_visual"],
                    weight=0.9,
                    crop_hint="half_left",
                ),
                ImageSlotSpec(
                    role=ImageSlotRole.AFTER,
                    target_element_roles=["supporting_visual", "hero_visual"],
                    weight=1.0,
                    crop_hint="half_right",
                ),
            ],
            analysis_lines=[
                AnalysisLineSpec(
                    kind=AnalysisLineKind.CUT,
                    stroke_swatch="renew_green",
                    x0=0.48,
                    y0=0.12,
                    x1=0.48,
                    y1=0.88,
                    weight_pt=1.5,
                    label="cut",
                ),
            ],
            max_details=0,
            source="icp:before_after",
        )

    if formula_id in {"layer_analysis", "drawing_dominant", "masterplan_focus"} or metaphor == "layered_site":
        return ImageCompositionPlan(
            mode=ImageCompositionMode.LAYERED_BASE,
            slots=[
                ImageSlotSpec(
                    role=ImageSlotRole.BASE_MAP,
                    target_element_roles=["hero_visual", "supporting_visual"],
                    weight=1.0,
                    crop_hint="full",
                ),
                ImageSlotSpec(
                    role=ImageSlotRole.DETAIL,
                    target_element_roles=["supporting_visual"],
                    weight=0.35,
                    crop_hint="inset_corner",
                ),
            ],
            analysis_lines=[
                AnalysisLineSpec(
                    kind=AnalysisLineKind.AXIS,
                    stroke_swatch="axis_line",
                    x0=0.15,
                    y0=0.2,
                    x1=0.85,
                    y1=0.75,
                    weight_pt=1.0,
                ),
                AnalysisLineSpec(
                    kind=AnalysisLineKind.BOUNDARY,
                    stroke_swatch="renew_green",
                    x0=0.2,
                    y0=0.65,
                    x1=0.8,
                    y1=0.65,
                    weight_pt=1.25,
                    opacity=0.7,
                ),
            ],
            max_details=1,
            source="icp:layered_base",
        )

    if formula_id == "axonometric_callout":
        return ImageCompositionPlan(
            mode=ImageCompositionMode.HERO_PLUS_DETAIL,
            slots=[
                ImageSlotSpec(
                    role=ImageSlotRole.HERO,
                    target_element_roles=["hero_visual", "supporting_visual"],
                    weight=1.0,
                ),
                ImageSlotSpec(
                    role=ImageSlotRole.DETAIL,
                    target_element_roles=["supporting_visual"],
                    weight=0.3,
                    crop_hint="inset_corner",
                ),
            ],
            analysis_lines=[
                AnalysisLineSpec(
                    kind=AnalysisLineKind.BOUNDARY,
                    stroke_swatch="axis_line",
                    x0=0.2,
                    y0=0.25,
                    x1=0.55,
                    y1=0.7,
                    weight_pt=1.0,
                    opacity=0.7,
                ),
            ],
            max_details=1,
            source="icp:axon",
        )

    if formula_id == "program_stack":
        return ImageCompositionPlan(
            mode=ImageCompositionMode.HERO_PLUS_DETAIL,
            slots=[
                ImageSlotSpec(
                    role=ImageSlotRole.HERO,
                    target_element_roles=["hero_visual"],
                    weight=0.9,
                ),
            ],
            analysis_lines=[
                AnalysisLineSpec(
                    kind=AnalysisLineKind.AXIS,
                    stroke_swatch="axis_line",
                    x0=0.35,
                    y0=0.15,
                    x1=0.35,
                    y1=0.85,
                    weight_pt=1.25,
                    label="stack",
                ),
            ],
            max_details=0,
            source="icp:program_stack",
        )

    if (
        formula_id in {"problem_evidence_conflict"}
        or metaphor == "fragment_to_network"
    ):
        return ImageCompositionPlan(
            mode=ImageCompositionMode.PHOTO_PLUS_ANALYSIS,
            slots=[
                ImageSlotSpec(
                    role=ImageSlotRole.HERO,
                    target_element_roles=["hero_visual", "supporting_visual"],
                    weight=1.0,
                    crop_hint="full",
                ),
                ImageSlotSpec(
                    role=ImageSlotRole.DETAIL,
                    target_element_roles=["supporting_visual"],
                    weight=0.3,
                    crop_hint="inset_corner",
                ),
            ],
            analysis_lines=[
                AnalysisLineSpec(
                    kind=AnalysisLineKind.CONFLICT,
                    stroke_swatch="alert_red",
                    x0=0.18,
                    y0=0.35,
                    x1=0.72,
                    y1=0.7,
                    weight_pt=1.75,
                    label="conflict",
                ),
                AnalysisLineSpec(
                    kind=AnalysisLineKind.FLOW,
                    stroke_swatch="axis_line",
                    x0=0.12,
                    y0=0.55,
                    x1=0.88,
                    y1=0.4,
                    weight_pt=1.1,
                    opacity=0.75,
                ),
            ],
            max_details=1,
            source="icp:photo_plus_analysis",
        )

    if formula_id in {"path_experience", "threshold_sequence"} or metaphor == "path_to_experience":
        return ImageCompositionPlan(
            mode=ImageCompositionMode.PHOTO_PLUS_ANALYSIS,
            slots=[
                ImageSlotSpec(
                    role=ImageSlotRole.HERO,
                    target_element_roles=["hero_visual"],
                    weight=1.0,
                ),
            ],
            analysis_lines=[
                AnalysisLineSpec(
                    kind=AnalysisLineKind.FLOW,
                    stroke_swatch="renew_green",
                    x0=0.1,
                    y0=0.7,
                    x1=0.9,
                    y1=0.35,
                    weight_pt=1.5,
                ),
                AnalysisLineSpec(
                    kind=AnalysisLineKind.AXIS,
                    stroke_swatch="axis_line",
                    x0=0.35,
                    y0=0.15,
                    x1=0.35,
                    y1=0.85,
                    weight_pt=0.9,
                    opacity=0.65,
                ),
            ],
            max_details=0,
            source="icp:path_experience",
        )

    if formula_id in {"phasing_timeline", "process_sequence"}:
        return ImageCompositionPlan(
            mode=ImageCompositionMode.HERO_PLUS_DETAIL,
            slots=[
                ImageSlotSpec(
                    role=ImageSlotRole.HERO,
                    target_element_roles=["hero_visual", "supporting_visual"],
                    weight=0.85,
                    crop_hint="full",
                ),
            ],
            analysis_lines=[
                AnalysisLineSpec(
                    kind=AnalysisLineKind.AXIS,
                    stroke_swatch="axis_line",
                    x0=0.1,
                    y0=0.55,
                    x1=0.9,
                    y1=0.55,
                    weight_pt=1.25,
                    label="phase",
                ),
            ],
            max_details=0,
            source="icp:phasing",
        )

    if formula_id == "evidence_triptych":
        return ImageCompositionPlan(
            mode=ImageCompositionMode.HERO_PLUS_DETAIL,
            slots=[
                ImageSlotSpec(
                    role=ImageSlotRole.HERO,
                    target_element_roles=["hero_visual"],
                    weight=1.0,
                ),
                ImageSlotSpec(
                    role=ImageSlotRole.DETAIL,
                    target_element_roles=["supporting_visual"],
                    weight=0.4,
                    crop_hint="inset_corner",
                ),
            ],
            analysis_lines=[
                AnalysisLineSpec(
                    kind=AnalysisLineKind.BOUNDARY,
                    stroke_swatch="alert_red",
                    x0=0.15,
                    y0=0.2,
                    x1=0.15,
                    y1=0.8,
                    weight_pt=1.5,
                ),
            ],
            max_details=1,
            source="icp:evidence_triptych",
        )

    if formula_id in {"hero_statement", "monument_image"} or emotion == "climax":
        return ImageCompositionPlan(
            mode=ImageCompositionMode.HERO_ONLY,
            slots=[
                ImageSlotSpec(
                    role=ImageSlotRole.HERO,
                    target_element_roles=["hero_visual"],
                    weight=1.0,
                    crop_hint="full",
                ),
            ],
            analysis_lines=[],
            max_details=0,
            source="icp:hero_clear",
        )

    if formula_id in {"core_expansion", "strategy_existing_transform"}:
        return ImageCompositionPlan(
            mode=ImageCompositionMode.HERO_PLUS_DETAIL,
            slots=[
                ImageSlotSpec(
                    role=ImageSlotRole.HERO,
                    target_element_roles=["hero_visual", "supporting_visual"],
                    weight=1.0,
                ),
                ImageSlotSpec(
                    role=ImageSlotRole.DETAIL,
                    target_element_roles=["supporting_visual"],
                    weight=0.35,
                    crop_hint="inset_corner",
                ),
            ],
            analysis_lines=[
                AnalysisLineSpec(
                    kind=AnalysisLineKind.BOUNDARY,
                    stroke_swatch="renew_green",
                    x0=0.25,
                    y0=0.25,
                    x1=0.75,
                    y1=0.75,
                    weight_pt=1.0,
                    opacity=0.55,
                ),
            ],
            max_details=1,
            source="icp:hero_plus_detail",
        )

    return ImageCompositionPlan(mode=ImageCompositionMode.NONE, source="icp:default")
