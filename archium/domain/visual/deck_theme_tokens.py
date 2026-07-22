"""Studio-facing deck-wide theme tokens mapped onto DesignSystem."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import PhotoTreatment

PageDensityToken = Literal["dense", "balanced", "spacious"]
IconStyleToken = Literal["line", "filled", "minimal"]


class DeckThemeTokens(DomainModel):
    """Flattened full-deck style controls for Studio Theme Panel.

    Only set fields are applied; ``None`` means keep the base DesignSystem value.
    """

    primary: str | None = None
    accent: str | None = None
    background: str | None = None
    title_font: str | None = None
    body_font: str | None = None
    title_scale: float | None = Field(default=None, ge=0.85, le=1.25)
    page_density: PageDensityToken | None = None
    corner_radius: float | None = Field(default=None, ge=0)
    line_weight: float | None = Field(default=None, gt=0)
    photo_treatment: PhotoTreatment | None = None
    icon_style: IconStyleToken | None = None


_DENSITY_SPACING_SCALE: dict[PageDensityToken, float] = {
    "dense": 0.85,
    "balanced": 1.0,
    "spacious": 1.2,
}

_ICON_STYLE_PRESETS: dict[IconStyleToken, tuple[float, float]] = {
    # marker_size, line_weight
    "line": (0.18, 0.9),
    "filled": (0.24, 0.75),
    "minimal": (0.16, 0.55),
}
