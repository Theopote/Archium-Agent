"""StylePreset model — office-aesthetic tokens without absolute coordinates."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import DensityLevel, LayoutFamily


class StylePresetId(StrEnum):
    """Built-in architecture presentation style presets (v0.3 Showcase)."""

    ARCHITECTURE_MINIMAL = "architecture_minimal"
    ARCHITECTURE_TECHNICAL = "architecture_technical"
    ARCHITECTURE_LUXURY = "architecture_luxury"
    ARCHITECTURE_ACADEMIC = "architecture_academic"
    ARCHITECTURE_URBAN = "architecture_urban"
    ARCHITECTURE_LANDSCAPE = "architecture_landscape"


class StylePreset(DomainModel):
    """Executable aesthetic overlay for DesignSystem + layout preference bias.

    Does not emit coordinates. Generators and validators consume the resulting
    DesignSystem tokens; DeckComposition / LayoutStylePreference consume density
    and family hints.
    """

    id: StylePresetId
    display_name: str = Field(min_length=1, max_length=80)
    description: str = ""
    density: DensityLevel = DensityLevel.BALANCED
    title_style: str = Field(default="quiet_bar", min_length=1, max_length=40)
    diagram_style: str = Field(default="line_sparse", min_length=1, max_length=40)

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
