"""VisualLanguageSpec — page-level visual rhetoric (Typography / Color / Decoration)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.visual_language.color_story import ColorStory
from archium.domain.visual.visual_language.decoration import DecorationRecipe
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
    decoration: DecorationRecipe = Field(default_factory=DecorationRecipe)
    symbols: list[ArchitecturalSymbolId] = Field(default_factory=list, max_length=6)
    image_behavior: ImageBehavior = ImageBehavior.INHERIT
    source: str = Field(default="rules", max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "typography": self.typography.as_dict(),
            "color_story": self.color_story.as_dict(),
            "decoration": self.decoration.as_dict(),
            "symbols": [item.value for item in self.symbols],
            "image_behavior": self.image_behavior.value,
            "source": self.source,
        }

    def summary_caption(self) -> str:
        """Short Studio caption."""
        bits = [f"字 `{self.typography.recipe.value}`"]
        roles = self.color_story.roles
        if roles:
            bits.append("色 " + "/".join(f"{k}={v}" for k, v in list(roles.items())[:3]))
        decos = self.decoration.decorations
        if decos:
            bits.append("饰 " + ",".join(d.value for d in decos[:3]))
        if self.symbols:
            bits.append("符 " + ",".join(s.value for s in self.symbols[:2]))
        return " · ".join(bits)
