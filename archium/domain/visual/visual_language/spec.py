"""VisualLanguageSpec — page-level visual rhetoric (Typography / Color / Decoration)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.visual_language.atmosphere import AtmosphereSpec
from archium.domain.visual.visual_language.color_composition import ColorComposition
from archium.domain.visual.visual_language.color_story import ColorStory
from archium.domain.visual.visual_language.decoration import DecorationRecipe
from archium.domain.visual.visual_language.graphic_motif import GraphicMotif
from archium.domain.visual.visual_language.image_composition import ImageCompositionPlan
from archium.domain.visual.visual_language.image_mask import ImageMaskSpec
from archium.domain.visual.visual_language.symbols import ArchitecturalSymbolId
from archium.domain.visual.visual_language.typography import TypographyRecipe


class ImageBehavior(StrEnum):
    INHERIT = "inherit"
    MASKED_OVERLAY = "masked_overlay"
    HERO_FULL = "hero_full"


class VisualLanguageSpec(DomainModel):
    """Director output: how this page should *speak* visually (not coordinates)."""

    typography: TypographyRecipe = Field(default_factory=TypographyRecipe)
    color_story: ColorStory = Field(default_factory=ColorStory)
    color_composition: ColorComposition | None = None
    graphic_motif: GraphicMotif | None = None
    decoration: DecorationRecipe = Field(default_factory=DecorationRecipe)
    symbols: list[ArchitecturalSymbolId] = Field(default_factory=list, max_length=6)
    primitive_ids: list[str] = Field(default_factory=list, max_length=12)
    asset_ids: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="ArchitecturalAsset ids suggested for this page.",
    )
    image_behavior: ImageBehavior = ImageBehavior.INHERIT
    image_mask: ImageMaskSpec = Field(default_factory=ImageMaskSpec)
    atmosphere: AtmosphereSpec = Field(default_factory=AtmosphereSpec)
    image_composition: ImageCompositionPlan = Field(default_factory=ImageCompositionPlan)
    source: str = Field(default="rules", max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "typography": self.typography.as_dict(),
            "color_story": self.color_story.as_dict(),
            "color_composition": (
                self.color_composition.as_dict() if self.color_composition else None
            ),
            "graphic_motif": self.graphic_motif.as_dict() if self.graphic_motif else None,
            "decoration": self.decoration.as_dict(),
            "symbols": [item.value for item in self.symbols],
            "primitive_ids": list(self.primitive_ids),
            "asset_ids": list(self.asset_ids),
            "image_behavior": self.image_behavior.value,
            "image_mask": self.image_mask.as_dict(),
            "atmosphere": self.atmosphere.as_dict(),
            "image_composition": self.image_composition.as_dict(),
            "source": self.source,
        }

    def summary_caption(self) -> str:
        """Short Studio caption."""
        bits = [f"字 `{self.typography.primary_role.value}`"]
        roles = self.color_story.roles
        if roles:
            bits.append("色 " + "/".join(f"{k}={v}" for k, v in list(roles.items())[:3]))
        if self.color_composition is not None:
            bits.append(f"配 `{self.color_composition.background_mode.value}`")
        if self.graphic_motif is not None:
            bits.append(f"母题 `{self.graphic_motif.motif_type.value}`")
        decos = self.decoration.decorations
        if decos:
            bits.append("饰 " + ",".join(d.value for d in decos[:3]))
        if self.symbols:
            bits.append("符 " + ",".join(s.value for s in self.symbols[:2]))
        if self.primitive_ids:
            bits.append("件 " + ",".join(self.primitive_ids[:3]))
        if self.asset_ids:
            bits.append("资 " + ",".join(self.asset_ids[:3]))
        if self.image_mask.kind.value != "none":
            bits.append(f"罩 `{self.image_mask.kind.value}`")
        if self.atmosphere.kind.value != "none":
            bits.append(f"底 `{self.atmosphere.kind.value}`")
        if self.image_composition.mode.value != "none":
            bits.append(f"图 `{self.image_composition.mode.value}`")
        return " · ".join(bits)
