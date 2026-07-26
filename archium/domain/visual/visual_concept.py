"""Page-level VisualConcept — architectural presentation metaphor (not Vision outpainting).

Distinct from ``VisualConceptBrief`` (image-generation brief). This model answers:
“Why does this page look like this?” before LayoutFamily coordinates.

``narrative`` (VisualNarrative) expands the metaphor into graphic / color / motion
behavior and recommended VisualPrimitive ids — Visual Rhetoric Engine core.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.visual_narrative import (
    GraphicBehavior,
    GraphicLayerMode,
    MotionDirection,
    VisualNarrative,
)


class VisualMetaphor(StrEnum):
    """Executable visual metaphors for architectural report pages.

    Keep the catalog small and deep — quality over quantity (target ~10).
    """

    FRAGMENT_TO_NETWORK = "fragment_to_network"
    EXISTING_TO_TRANSFORMATION = "existing_to_transformation"
    LAYERED_SITE = "layered_site"
    CORE_TO_EXPANSION = "core_to_expansion"
    PATH_TO_EXPERIENCE = "path_to_experience"
    MONUMENT_SINGLE = "monument_single"
    BEFORE_AFTER_CUT = "before_after_cut"
    QUIET_ARGUMENT = "quiet_argument"


class GraphicLanguage(StrEnum):
    ARCHITECTURAL_DIAGRAM = "architectural_diagram"
    PHOTO_EVIDENCE = "photo_evidence"
    DRAWING_BOARD = "drawing_board"
    ATMOSPHERE_HERO = "atmosphere_hero"


class ConceptImageStrategy(StrEnum):
    """How images narrate — not filter parameters."""

    CONTRAST_BEFORE_AFTER = "contrast_before_after"
    HERO_SINGLE = "hero_single"
    EVIDENCE_GRID = "evidence_grid"
    DRAWING_WITH_CALLOUTS = "drawing_with_callouts"


class VisualConcept(DomainModel):
    """Page visual concept — metaphor + optional full VisualNarrative."""

    concept_name: str = Field(min_length=1, max_length=120)
    visual_metaphor: VisualMetaphor
    color_story: list[str] = Field(default_factory=list, max_length=6)
    graphic_language: GraphicLanguage = GraphicLanguage.ARCHITECTURAL_DIAGRAM
    image_strategy: ConceptImageStrategy = ConceptImageStrategy.EVIDENCE_GRID
    drawing_min_area_ratio: float | None = Field(default=None, ge=0.2, le=0.9)
    whitespace_hint: float | None = Field(default=None, ge=0.05, le=0.6)
    narrative: VisualNarrative | None = None
    source: str = Field(default="rules", min_length=1, max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "concept_name": self.concept_name,
            "visual_metaphor": self.visual_metaphor.value,
            "color_story": list(self.color_story),
            "graphic_language": self.graphic_language.value,
            "image_strategy": self.image_strategy.value,
            "drawing_min_area_ratio": self.drawing_min_area_ratio,
            "whitespace_hint": self.whitespace_hint,
            "narrative": self.narrative.as_dict() if self.narrative else None,
            "source": self.source,
        }


FRAGMENT_TO_NETWORK_NARRATIVE = VisualNarrative(
    name="fragment_to_network",
    metaphor="fragment becomes connection",
    graphic_language=GraphicBehavior(
        geometry="broken_lines_to_curve",
        direction=MotionDirection.CONVERGING,
        layer=GraphicLayerMode.BEFORE_AFTER,
    ),
    color_roles={
        "existing": "gray",
        "problem": "red",
        "conflict": "red",
        "future": "white",
        "solution": "white",
    },
    recommended_components=[
        "flow_line",
        "node",
        "overlay_map",
        "transition_arrow",
        "axis_line",
        "circulation",
    ],
    source="grammar_v1:fragment_to_network",
)

FRAGMENT_TO_NETWORK_CONCEPT = VisualConcept(
    concept_name="Broken Flow → Connected Campus",
    visual_metaphor=VisualMetaphor.FRAGMENT_TO_NETWORK,
    color_story=["gray", "red", "white"],
    graphic_language=GraphicLanguage.ARCHITECTURAL_DIAGRAM,
    image_strategy=ConceptImageStrategy.CONTRAST_BEFORE_AFTER,
    drawing_min_area_ratio=0.45,
    whitespace_hint=0.22,
    narrative=FRAGMENT_TO_NETWORK_NARRATIVE,
    source="grammar_v1:fragment_to_network",
)

EXISTING_TO_TRANSFORMATION_NARRATIVE = VisualNarrative(
    name="existing_to_transformation",
    metaphor="existing fabric receives a precise intervention",
    graphic_language=GraphicBehavior(
        geometry="photo_plus_analysis_line",
        direction=MotionDirection.SEQUENTIAL,
        layer=GraphicLayerMode.BEFORE_AFTER,
    ),
    color_roles={
        "existing": "gray",
        "intervention": "renew_green",
        "future": "warm_white",
    },
    recommended_components=[
        "thin_rule",
        "transition_arrow",
        "overlay_map",
        "section_index",
    ],
    source="grammar_v1:existing_to_transformation",
)

EXISTING_TO_TRANSFORMATION_CONCEPT = VisualConcept(
    concept_name="Existing → Transformation",
    visual_metaphor=VisualMetaphor.EXISTING_TO_TRANSFORMATION,
    color_story=["gray", "renew_green", "warm_white"],
    graphic_language=GraphicLanguage.PHOTO_EVIDENCE,
    image_strategy=ConceptImageStrategy.CONTRAST_BEFORE_AFTER,
    drawing_min_area_ratio=0.5,
    whitespace_hint=0.2,
    narrative=EXISTING_TO_TRANSFORMATION_NARRATIVE,
    source="grammar_v1:existing_to_transformation",
)

LAYERED_SITE_NARRATIVE = VisualNarrative(
    name="layered_site",
    metaphor="base map accumulates analysis layers into a system reading",
    graphic_language=GraphicBehavior(
        geometry="base_plus_overlay_stack",
        direction=MotionDirection.LAYERED,
        layer=GraphicLayerMode.OVERLAY,
    ),
    color_roles={
        "existing": "stone_gray",
        "intervention": "renew_green",
        "accent": "ink_black",
    },
    recommended_components=["overlay_map", "axis_line", "node", "thin_rule"],
    source="grammar_v1:layered_site",
)

LAYERED_SITE_CONCEPT = VisualConcept(
    concept_name="Layer → System",
    visual_metaphor=VisualMetaphor.LAYERED_SITE,
    color_story=["stone_gray", "renew_green", "ink_black"],
    graphic_language=GraphicLanguage.DRAWING_BOARD,
    image_strategy=ConceptImageStrategy.DRAWING_WITH_CALLOUTS,
    drawing_min_area_ratio=0.6,
    whitespace_hint=0.18,
    narrative=LAYERED_SITE_NARRATIVE,
    source="grammar_v1:layered_site",
)

PATH_TO_EXPERIENCE_NARRATIVE = VisualNarrative(
    name="path_to_experience",
    metaphor="path, node, and sequence become lived spatial experience",
    graphic_language=GraphicBehavior(
        geometry="path_nodes_sequence",
        direction=MotionDirection.SEQUENTIAL,
        layer=GraphicLayerMode.SEQUENCE,
    ),
    color_roles={
        "existing": "gray",
        "conflict": "red",
        "future": "renew_green",
    },
    recommended_components=[
        "flow_line",
        "node",
        "circulation",
        "entrance",
        "axis_line",
    ],
    source="grammar_v1:path_to_experience",
)

PATH_TO_EXPERIENCE_CONCEPT = VisualConcept(
    concept_name="Path → Experience",
    visual_metaphor=VisualMetaphor.PATH_TO_EXPERIENCE,
    color_story=["gray", "red", "renew_green"],
    graphic_language=GraphicLanguage.ARCHITECTURAL_DIAGRAM,
    image_strategy=ConceptImageStrategy.DRAWING_WITH_CALLOUTS,
    drawing_min_area_ratio=0.5,
    whitespace_hint=0.2,
    narrative=PATH_TO_EXPERIENCE_NARRATIVE,
    source="grammar_v1:path_to_experience",
)

CORE_TO_EXPANSION_NARRATIVE = VisualNarrative(
    name="core_to_expansion",
    metaphor="a dense core grows outward into a controlled expansion",
    graphic_language=GraphicBehavior(
        geometry="core_radial_growth",
        direction=MotionDirection.EXPANDING,
        layer=GraphicLayerMode.SINGLE,
    ),
    color_roles={
        "existing": "ink_black",
        "intervention": "renew_green",
        "future": "warm_white",
    },
    recommended_components=[
        "node",
        "transition_arrow",
        "overlay_map",
        "thin_rule",
        "section_index",
    ],
    source="grammar_v1:core_to_expansion",
)

CORE_TO_EXPANSION_CONCEPT = VisualConcept(
    concept_name="Core → Expansion",
    visual_metaphor=VisualMetaphor.CORE_TO_EXPANSION,
    color_story=["ink_black", "renew_green", "warm_white"],
    graphic_language=GraphicLanguage.ATMOSPHERE_HERO,
    image_strategy=ConceptImageStrategy.HERO_SINGLE,
    drawing_min_area_ratio=0.55,
    whitespace_hint=0.25,
    narrative=CORE_TO_EXPANSION_NARRATIVE,
    source="grammar_v1:core_to_expansion",
)

QUIET_ARGUMENT_NARRATIVE = VisualNarrative(
    name="quiet_argument",
    metaphor="one claim, restrained evidence, no decoration noise",
    graphic_language=GraphicBehavior(
        geometry="single_statement_bar",
        direction=MotionDirection.STATIC,
        layer=GraphicLayerMode.SINGLE,
    ),
    color_roles={
        "neutral": "ink_black",
        "accent": "stone_gray",
    },
    recommended_components=["thin_rule", "section_index"],
    source="grammar_v1:quiet_argument",
)

QUIET_ARGUMENT_CONCEPT = VisualConcept(
    concept_name="Quiet Argument",
    visual_metaphor=VisualMetaphor.QUIET_ARGUMENT,
    color_story=["ink_black", "stone_gray"],
    graphic_language=GraphicLanguage.PHOTO_EVIDENCE,
    image_strategy=ConceptImageStrategy.EVIDENCE_GRID,
    drawing_min_area_ratio=0.35,
    whitespace_hint=0.35,
    narrative=QUIET_ARGUMENT_NARRATIVE,
    source="grammar_v1:quiet_argument",
)
