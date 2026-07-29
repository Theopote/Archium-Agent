"""Asset Presentation Readiness — whether an asset is fit to show on a slide.

Distinct from cognition/workstream ``presentation_ready`` and from PowerPoint
shape placeholders (``shape.is_placeholder``).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class AssetPresentationRole(StrEnum):
    """Recommended slot for a visually assessed asset."""

    HERO_DRAWING = "hero_drawing"
    HERO_PHOTO = "hero_photo"
    EVIDENCE_PRIMARY = "evidence_primary"
    EVIDENCE_SUPPORTING = "evidence_supporting"
    REFERENCE_ONLY = "reference_only"
    UNSUITABLE = "unsuitable"


class AssetPresentationReadiness(DomainModel):
    """Per-asset gate for hero / evidence / drawing display."""

    is_placeholder: bool = False
    visual_information_density: float = Field(default=0.0, ge=0.0, le=1.0)
    readable_at_slide_scale: bool = False
    recommended_role: AssetPresentationRole = AssetPresentationRole.UNSUITABLE
    min_display_area_ratio: float = Field(default=0.35, ge=0.05, le=1.0)
    presentation_ready: bool = False
    pixel_analyzed: bool = False
    reasons: list[str] = Field(default_factory=list)

    def to_metadata(self) -> dict[str, object]:
        return self.model_dump(mode="json")


# Stored under Asset.metadata[ASSET_PRESENTATION_READINESS_KEY] when cached.
ASSET_PRESENTATION_READINESS_KEY = "asset_presentation_readiness"
