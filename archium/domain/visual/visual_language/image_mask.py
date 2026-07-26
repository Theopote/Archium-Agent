"""Image mask rhetoric — crop / silhouette / fade (not PhotoTreatment filters)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class ImageMaskKind(StrEnum):
    NONE = "none"
    ROUNDED = "rounded"
    CIRCLE = "circle"
    GRADIENT_FADE = "gradient_fade"
    SILHOUETTE = "silhouette"
    CUTOUT = "cutout"


class ImageMaskSpec(DomainModel):
    """How primary images should be masked on this page."""

    kind: ImageMaskKind = ImageMaskKind.NONE
    # Corner radius in page inches (rounded) or ignored for circle.
    corner_radius: float = Field(default=0.08, ge=0.0, le=2.0)
    # Soft edge / silhouette strength 0–1 (renderer maps to opacity overlay).
    edge_softness: float = Field(default=0.35, ge=0.0, le=1.0)
    target_roles: list[str] = Field(
        default_factory=lambda: ["hero_visual", "supporting_visual"],
        max_length=6,
    )
    source: str = Field(default="rules", max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "corner_radius": self.corner_radius,
            "edge_softness": self.edge_softness,
            "target_roles": list(self.target_roles),
            "source": self.source,
        }


def mask_for_image_behavior(behavior: str) -> ImageMaskSpec:
    """Map VisualLanguage ImageBehavior → default ImageMaskSpec."""
    if behavior == "masked_overlay":
        return ImageMaskSpec(
            kind=ImageMaskKind.GRADIENT_FADE,
            corner_radius=0.06,
            edge_softness=0.45,
            source="image_behavior:masked_overlay",
        )
    if behavior == "hero_full":
        return ImageMaskSpec(
            kind=ImageMaskKind.NONE,
            corner_radius=0.0,
            edge_softness=0.0,
            source="image_behavior:hero_full",
        )
    return ImageMaskSpec(kind=ImageMaskKind.NONE, source="image_behavior:inherit")
