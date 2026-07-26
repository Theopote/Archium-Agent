"""Page-level VisualConcept — architectural presentation metaphor (not Vision outpainting).

Distinct from ``VisualConceptBrief`` (image-generation brief). This model answers:
“Why does this page look like this?” before LayoutFamily coordinates.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class VisualMetaphor(StrEnum):
    """Executable visual metaphors for architectural report pages."""

    FRAGMENT_TO_NETWORK = "fragment_to_network"
    MONUMENT_SINGLE = "monument_single"
    LAYERED_SITE = "layered_site"
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
    """Page visual concept — metaphor and graphic language for one slide."""

    concept_name: str = Field(min_length=1, max_length=120)
    visual_metaphor: VisualMetaphor
    color_story: list[str] = Field(default_factory=list, max_length=6)
    graphic_language: GraphicLanguage = GraphicLanguage.ARCHITECTURAL_DIAGRAM
    image_strategy: ConceptImageStrategy = ConceptImageStrategy.EVIDENCE_GRID
    drawing_min_area_ratio: float | None = Field(default=None, ge=0.2, le=0.9)
    whitespace_hint: float | None = Field(default=None, ge=0.05, le=0.6)
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
            "source": self.source,
        }


# Catalog of rule-built concepts (extend carefully; no new Agent).
FRAGMENT_TO_NETWORK_CONCEPT = VisualConcept(
    concept_name="Broken Flow → Connected Campus",
    visual_metaphor=VisualMetaphor.FRAGMENT_TO_NETWORK,
    color_story=["gray", "red", "white"],
    graphic_language=GraphicLanguage.ARCHITECTURAL_DIAGRAM,
    image_strategy=ConceptImageStrategy.CONTRAST_BEFORE_AFTER,
    drawing_min_area_ratio=0.45,
    whitespace_hint=0.22,
    source="grammar_v1:fragment_to_network",
)
