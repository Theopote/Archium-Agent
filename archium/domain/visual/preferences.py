"""User visual preferences for composition (small, intentional surface)."""

from __future__ import annotations

from archium.domain._base import DomainModel
from archium.domain.visual.enums import (
    DecorationLevel,
    DensityLevel,
    DrawingDisplayMode,
    FormalityLevel,
    PresentationContext,
    VisualEmphasis,
    WhitespacePreference,
)


class VisualPreferences(DomainModel):
    """First-edition user knobs — avoid exposing dozens of design parameters."""

    density: DensityLevel = DensityLevel.BALANCED
    visual_emphasis: VisualEmphasis = VisualEmphasis.BALANCED
    formality: FormalityLevel = FormalityLevel.PROFESSIONAL
    decoration_level: DecorationLevel = DecorationLevel.LOW
    whitespace_preference: WhitespacePreference = WhitespacePreference.BALANCED
    drawing_display_mode: DrawingDisplayMode = DrawingDisplayMode.CLEAR
    presentation_context: PresentationContext = PresentationContext.CLIENT_REVIEW
