"""Composition Strategy — architectural visual composition as structured design judgment.

This module defines how a single slide should be visually structured from an
architectural design perspective, not just element placement. It captures the
design thinking that precedes layout geometry.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field

from archium.domain._base import DomainModel


class CompositionAxis(StrEnum):
    """Primary structural axis organizing the composition."""

    HORIZONTAL = "horizontal"  # Left-right flow, landscape emphasis
    VERTICAL = "vertical"  # Top-down hierarchy, vertical section
    DIAGONAL = "diagonal"  # Dynamic movement, architectural section cut
    RADIAL = "radial"  # Central focus with radiating elements
    NONE = "none"  # No dominant axis, grid or scattered


class VisualTension(StrEnum):
    """The structural balance strategy of the composition."""

    SYMMETRIC = "symmetric"  # Mirrored balance, formal
    ASYMMETRIC = "asymmetric"  # Unequal but balanced, editorial
    DYNAMIC = "dynamic"  # Intentional imbalance, movement
    STATIC = "static"  # Stable, grounded, architectural plan view


class VisualBalance(StrEnum):
    """Weight distribution across the page."""

    CENTERED = "centered"  # Central mass, symmetry
    LEFT_WEIGHTED = "left_weighted"  # Western reading, editorial
    RIGHT_WEIGHTED = "right_weighted"  # Reveal, unexpected
    TOP_HEAVY = "top_heavy"  # Hero image or title dominance
    BOTTOM_ANCHORED = "bottom_anchored"  # Grounded, landscape baseline


class ReadingPathType(StrEnum):
    """Expected audience eye movement through the composition."""

    LINEAR_LTR = "linear_ltr"  # Left-to-right, simple narrative
    Z_PATTERN = "z_pattern"  # Title → hero → text, classic editorial
    F_PATTERN = "f_pattern"  # Scan-heavy, data or list
    FOCAL_RADIAL = "focal_radial"  # Central hero outward
    LAYERED = "layered"  # Background → midground → foreground depth


class WhiteSpaceStrategy(StrEnum):
    """How negative space is deployed for emphasis and breathing."""

    GENEROUS = "generous"  # Architecture cover, monumental
    BALANCED = "balanced"  # Standard analysis page
    COMPACT = "compact"  # Data-dense, technical
    STRATEGIC = "strategic"  # Localized negative space for emphasis


class ImageRole(StrEnum):
    """The design function of imagery in this composition."""

    DOMINANT = "dominant"  # Hero, primary visual narrative
    SUPPORTING = "supporting"  # Evidence, context
    AMBIENT = "ambient"  # Background texture, mood
    EVIDENCE = "evidence"  # Technical proof, diagram
    ABSENT = "absent"  # Text or data only


class TypographyRole(StrEnum):
    """The design function of type in this composition."""

    HERO = "hero"  # Large title as primary visual element
    EDITORIAL = "editorial"  # Balanced text and image
    DATA_LABEL = "data_label"  # Annotations, technical callouts
    NARRATIVE = "narrative"  # Body copy, explanation
    MINIMAL = "minimal"  # Sparse labels only


class LayeringStrategy(StrEnum):
    """Depth strategy for composition."""

    FLAT = "flat"  # Single plane, diagram clarity
    SUBTLE_DEPTH = "subtle_depth"  # Slight overlap, shadows
    PRONOUNCED = "pronounced"  # Strong foreground/background separation


class MarginsStrategy(StrEnum):
    """Edge treatment and breathing room."""

    GENEROUS = "generous"  # Wide margins, luxury
    STANDARD = "standard"  # Balanced professional
    TIGHT = "tight"  # Maximum content density
    ASYMMETRIC = "asymmetric"  # One side open, editorial


class CompositionStrategy(DomainModel):
    """Structured architectural composition strategy for a single slide.

    This captures the design judgment that architects apply when creating
    presentation layouts — not CSS properties, but visual narrative intent.
    """

    # High-level archetype
    archetype: str = Field(
        min_length=1,
        max_length=100,
        description="Design pattern name: architectural_editorial, data_narrative, diagram_reveal, etc.",
    )

    # Compositional structure
    dominant_axis: CompositionAxis = Field(
        description="Primary structural axis organizing the composition",
    )
    focal_point: tuple[float, float] | None = Field(
        default=None,
        description="Visual center of gravity as (x%, y%) from top-left; None = no single focus",
    )
    visual_hierarchy: list[str] = Field(
        default_factory=list,
        description="Ordered importance: ['hero_image', 'title', 'annotation']",
    )
    reading_path: ReadingPathType = Field(
        description="Expected eye movement pattern through the page",
    )

    # Visual forces
    tension: VisualTension = Field(
        description="Balance strategy: symmetric, asymmetric, dynamic, static",
    )
    balance: VisualBalance = Field(
        description="Weight distribution across the page",
    )
    rhythm: str = Field(
        default="varied",
        description="Element repetition: repetitive, varied, progressive",
    )

    # Element roles (design intent, not implementation)
    image_role: ImageRole = Field(
        description="How imagery functions in this composition",
    )
    typography_role: TypographyRole = Field(
        description="How type functions in this composition",
    )
    diagram_role: str | None = Field(
        default=None,
        description="Diagram treatment if present: annotated, standalone, layered, etc.",
    )

    # Spatial strategy
    white_space: WhiteSpaceStrategy = Field(
        description="How negative space is deployed",
    )
    margins: MarginsStrategy = Field(
        default=MarginsStrategy.STANDARD,
        description="Edge treatment and breathing room",
    )
    layering: LayeringStrategy = Field(
        default=LayeringStrategy.FLAT,
        description="Depth strategy for composition",
    )

    # Architectural-specific guidance
    drawing_priority: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.5,
        description="Importance of technical drawings vs. photos (0=photos, 1=drawings)",
    )
    precision_level: str = Field(
        default="balanced",
        description="Technical precision: loose, balanced, precise",
    )
    annotation_density: str = Field(
        default="moderate",
        description="Callout/label density: sparse, moderate, dense",
    )

    def is_hero_dominated(self) -> bool:
        """True when composition is dominated by a single large visual element."""
        return self.image_role == ImageRole.DOMINANT and self.balance in (
            VisualBalance.CENTERED,
            VisualBalance.TOP_HEAVY,
        )

    def is_editorial_style(self) -> bool:
        """True when composition follows editorial magazine layout principles."""
        return (
            self.tension == VisualTension.ASYMMETRIC
            and self.balance == VisualBalance.LEFT_WEIGHTED
            and self.reading_path == ReadingPathType.Z_PATTERN
        )

    def is_technical_diagram(self) -> bool:
        """True when composition prioritizes technical clarity over aesthetics."""
        return (
            self.image_role == ImageRole.EVIDENCE
            and self.layering == LayeringStrategy.FLAT
            and self.drawing_priority >= 0.7
        )

    def is_spacious(self) -> bool:
        """True when composition emphasizes generous negative space."""
        return self.white_space in (
            WhiteSpaceStrategy.GENEROUS,
            WhiteSpaceStrategy.STRATEGIC,
        ) and self.margins in (MarginsStrategy.GENEROUS, MarginsStrategy.STANDARD)


# Predefined composition archetypes for common architectural presentation patterns
ARCHETYPE_PRESETS: dict[str, CompositionStrategy] = {
    "architectural_editorial": CompositionStrategy(
        archetype="architectural_editorial",
        dominant_axis=CompositionAxis.HORIZONTAL,
        focal_point=(0.35, 0.45),
        visual_hierarchy=["hero_image", "title", "body_text"],
        reading_path=ReadingPathType.Z_PATTERN,
        tension=VisualTension.ASYMMETRIC,
        balance=VisualBalance.LEFT_WEIGHTED,
        rhythm="varied",
        image_role=ImageRole.DOMINANT,
        typography_role=TypographyRole.EDITORIAL,
        white_space=WhiteSpaceStrategy.GENEROUS,
        margins=MarginsStrategy.GENEROUS,
        layering=LayeringStrategy.SUBTLE_DEPTH,
        drawing_priority=0.3,
        precision_level="balanced",
        annotation_density="sparse",
    ),
    "technical_diagram": CompositionStrategy(
        archetype="technical_diagram",
        dominant_axis=CompositionAxis.VERTICAL,
        focal_point=None,
        visual_hierarchy=["diagram", "title", "annotations"],
        reading_path=ReadingPathType.F_PATTERN,
        tension=VisualTension.SYMMETRIC,
        balance=VisualBalance.CENTERED,
        rhythm="repetitive",
        image_role=ImageRole.EVIDENCE,
        typography_role=TypographyRole.DATA_LABEL,
        diagram_role="annotated",
        white_space=WhiteSpaceStrategy.BALANCED,
        margins=MarginsStrategy.STANDARD,
        layering=LayeringStrategy.FLAT,
        drawing_priority=0.9,
        precision_level="precise",
        annotation_density="dense",
    ),
    "hero_statement": CompositionStrategy(
        archetype="hero_statement",
        dominant_axis=CompositionAxis.NONE,
        focal_point=(0.5, 0.5),
        visual_hierarchy=["hero_image", "title"],
        reading_path=ReadingPathType.FOCAL_RADIAL,
        tension=VisualTension.STATIC,
        balance=VisualBalance.CENTERED,
        rhythm="progressive",
        image_role=ImageRole.DOMINANT,
        typography_role=TypographyRole.HERO,
        white_space=WhiteSpaceStrategy.GENEROUS,
        margins=MarginsStrategy.GENEROUS,
        layering=LayeringStrategy.SUBTLE_DEPTH,
        drawing_priority=0.2,
        precision_level="loose",
        annotation_density="sparse",
    ),
    "data_narrative": CompositionStrategy(
        archetype="data_narrative",
        dominant_axis=CompositionAxis.HORIZONTAL,
        focal_point=None,
        visual_hierarchy=["chart", "title", "insight_text"],
        reading_path=ReadingPathType.LINEAR_LTR,
        tension=VisualTension.SYMMETRIC,
        balance=VisualBalance.CENTERED,
        rhythm="repetitive",
        image_role=ImageRole.SUPPORTING,
        typography_role=TypographyRole.DATA_LABEL,
        white_space=WhiteSpaceStrategy.COMPACT,
        margins=MarginsStrategy.TIGHT,
        layering=LayeringStrategy.FLAT,
        drawing_priority=0.4,
        precision_level="precise",
        annotation_density="moderate",
    ),
    "section_reveal": CompositionStrategy(
        archetype="section_reveal",
        dominant_axis=CompositionAxis.DIAGONAL,
        focal_point=(0.4, 0.6),
        visual_hierarchy=["section_drawing", "title", "key_labels"],
        reading_path=ReadingPathType.LAYERED,
        tension=VisualTension.DYNAMIC,
        balance=VisualBalance.LEFT_WEIGHTED,
        rhythm="progressive",
        image_role=ImageRole.DOMINANT,
        typography_role=TypographyRole.DATA_LABEL,
        diagram_role="layered",
        white_space=WhiteSpaceStrategy.STRATEGIC,
        margins=MarginsStrategy.ASYMMETRIC,
        layering=LayeringStrategy.PRONOUNCED,
        drawing_priority=0.95,
        precision_level="precise",
        annotation_density="moderate",
    ),
}


def get_preset_strategy(archetype: str) -> CompositionStrategy | None:
    """Retrieve a predefined composition strategy by archetype name."""
    return ARCHETYPE_PRESETS.get(archetype)


def suggest_strategy_for_content(
    *,
    has_large_image: bool,
    has_technical_drawing: bool,
    has_data_chart: bool,
    text_density: str,
) -> str:
    """Heuristic to suggest an appropriate archetype based on content analysis.

    Returns archetype name suitable for get_preset_strategy().
    """
    if has_technical_drawing and text_density in ("low", "moderate"):
        if has_large_image:
            return "section_reveal"
        return "technical_diagram"
    if has_data_chart:
        return "data_narrative"
    if has_large_image and text_density == "low":
        return "hero_statement"
    if has_large_image:
        return "architectural_editorial"
    # Default fallback
    return "architectural_editorial"
