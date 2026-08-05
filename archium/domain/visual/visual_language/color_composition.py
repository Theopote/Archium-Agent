"""ColorComposition — page-level color orchestration (VQ-002).

Distinct from ``ColorSystem`` (static tokens) and ``ColorStory`` (semantic
role → swatch narrative). This model answers: what *ratios* and *modes*
should dominate this page, so color is composed rather than merely themed.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class BackgroundMode(StrEnum):
    LIGHT = "light"
    TINTED = "tinted"
    DARK = "dark"
    ACCENT_WASH = "accent_wash"
    MONOCHROME = "monochrome"


class ColorComposition(DomainModel):
    """Executable page color mix — ratios are targets, not pixel measurements."""

    background_mode: BackgroundMode = BackgroundMode.TINTED
    dominant_token: str = Field(default="background", min_length=1)
    support_tokens: list[str] = Field(default_factory=list, max_length=4)
    accent_token: str = Field(default="accent", min_length=1)

    # Target area ratios (0–1); enforcement is soft via wash / decoration / title.
    background_ratio: float = Field(default=0.75, ge=0.4, le=0.95)
    dominant_ratio: float = Field(default=0.18, ge=0.0, le=0.5)
    accent_ratio: float = Field(default=0.05, ge=0.0, le=0.35)

    image_tint: str | None = Field(
        default=None,
        description="Optional unify cue: none | cool | warm | mono",
    )
    drawing_recolor: str | None = Field(
        default=None,
        description="Optional drawing stroke cue: primary | accent | ink | none",
    )
    section_override: bool = False
    # Resolved hex for scene background (filled by composer).
    background_hex: str | None = None
    accent_hex: str | None = None
    primary_text_hex: str | None = None
    source: str = Field(default="rules", max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "background_mode": self.background_mode.value,
            "dominant_token": self.dominant_token,
            "support_tokens": list(self.support_tokens),
            "accent_token": self.accent_token,
            "background_ratio": self.background_ratio,
            "dominant_ratio": self.dominant_ratio,
            "accent_ratio": self.accent_ratio,
            "image_tint": self.image_tint,
            "drawing_recolor": self.drawing_recolor,
            "section_override": self.section_override,
            "background_hex": self.background_hex,
            "accent_hex": self.accent_hex,
            "primary_text_hex": self.primary_text_hex,
            "source": self.source,
        }
