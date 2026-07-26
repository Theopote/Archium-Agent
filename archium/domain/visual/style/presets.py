"""StylePreset model — office aesthetic + narrative personality + content policy.

Visual tokens alone are not enough: Technical means evidence-first, Luxury means
experience-first. ContentPolicy caps refuse dense “garbage pages” at the source.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import DensityLevel, LayoutFamily
from archium.domain.visual.page_direction import CopyBudget


class StylePresetId(StrEnum):
    """Built-in architecture presentation style presets (v0.3 Showcase)."""

    ARCHITECTURE_MINIMAL = "architecture_minimal"
    ARCHITECTURE_TECHNICAL = "architecture_technical"
    ARCHITECTURE_LUXURY = "architecture_luxury"
    ARCHITECTURE_ACADEMIC = "architecture_academic"
    ARCHITECTURE_URBAN = "architecture_urban"
    ARCHITECTURE_LANDSCAPE = "architecture_landscape"


class NarrativeLogic(StrEnum):
    """How the deck argues — not a color choice."""

    EVIDENCE_FIRST = "evidence_first"
    EXPERIENCE_FIRST = "experience_first"
    ARGUMENT_FIRST = "argument_first"
    ANALYSIS_FIRST = "analysis_first"


class EmotionLevel(StrEnum):
    """Emotional volume of the presentation personality."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ImageRole(StrEnum):
    """Relative weight of imagery vs text/drawings."""

    SUPPORTING = "supporting"
    EQUAL = "equal"
    DOMINANT = "dominant"


class PresentationPersonality(DomainModel):
    """Narrative personality encoded on a StylePreset (executable, not prose)."""

    logic: NarrativeLogic = NarrativeLogic.EVIDENCE_FIRST
    emotion: EmotionLevel = EmotionLevel.LOW
    image_role: ImageRole = ImageRole.SUPPORTING


class StyleContentPolicy(DomainModel):
    """Deck-default content caps — Page Director CopyBudget takes the stricter bound."""

    max_title_chars: int = Field(default=36, ge=8, le=120)
    max_message_chars: int = Field(default=100, ge=20, le=400)
    max_key_points: int = Field(default=3, ge=0, le=12)
    max_body_blocks: int = Field(default=2, ge=0, le=8)
    max_images: int = Field(default=4, ge=0, le=12)
    max_diagrams: int = Field(default=2, ge=0, le=8)
    preferred_whitespace: float | None = Field(default=None, ge=0.0, le=0.6)

    def to_copy_budget(self) -> CopyBudget:
        return CopyBudget(
            max_title_chars=self.max_title_chars,
            max_message_chars=self.max_message_chars,
            max_key_points=self.max_key_points,
            max_body_blocks=self.max_body_blocks,
        )


def merge_copy_budget_stricter(
    left: CopyBudget, right: CopyBudget | StyleContentPolicy
) -> CopyBudget:
    """Intersection of budgets — every cap uses the tighter (smaller) value."""
    other = right.to_copy_budget() if isinstance(right, StyleContentPolicy) else right
    return CopyBudget(
        max_title_chars=min(left.max_title_chars, other.max_title_chars),
        max_message_chars=min(left.max_message_chars, other.max_message_chars),
        max_key_points=min(left.max_key_points, other.max_key_points),
        max_body_blocks=min(left.max_body_blocks, other.max_body_blocks),
    )


class StylePreset(DomainModel):
    """Executable aesthetic + narrative overlay for DesignSystem / Director.

    Does not emit coordinates. Generators and validators consume DesignSystem
    tokens; DeckComposition / LayoutStylePreference consume density and family
    hints; Page Director merges ``content_policy`` into CopyBudget (stricter wins).
    """

    id: StylePresetId
    display_name: str = Field(min_length=1, max_length=80)
    description: str = ""
    density: DensityLevel = DensityLevel.BALANCED
    title_style: str = Field(default="quiet_bar", min_length=1, max_length=40)
    diagram_style: str = Field(default="line_sparse", min_length=1, max_length=40)

    # Narrative personality (beyond visual tokens)
    presentation_personality: PresentationPersonality = Field(
        default_factory=PresentationPersonality
    )
    content_policy: StyleContentPolicy = Field(default_factory=StyleContentPolicy)

    # Typography
    title_scale: float = Field(default=1.0, gt=0.5, le=1.6)
    body_pt: float | None = Field(default=None, gt=8.0, le=24.0)
    letter_spacing_bias: float = Field(default=0.0, ge=-0.5, le=1.0)

    # Spacing / page
    margin_scale: float = Field(default=1.0, gt=0.5, le=1.8)
    gutter_scale: float = Field(default=1.0, gt=0.5, le=1.8)
    spacing_scale: float = Field(default=1.0, gt=0.5, le=1.8)

    # Image / validation thresholds
    hero_min_area_ratio: float | None = Field(default=None, ge=0.2, le=0.85)
    min_whitespace_ratio: float | None = Field(default=None, ge=0.0, le=0.5)
    max_whitespace_ratio: float | None = Field(default=None, ge=0.2, le=0.85)
    max_accent_ratio: float = Field(default=0.08, ge=0.0, le=0.3)

    # Partial ColorSystem overrides (token → hex)
    colors: dict[str, str] = Field(default_factory=dict)

    preferred_layout_families: tuple[LayoutFamily, ...] = ()
    forbidden_layout_families: tuple[LayoutFamily, ...] = ()
    forbidden_style_tags: tuple[str, ...] = ()
