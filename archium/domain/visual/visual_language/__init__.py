"""Architectural presentation visual language — rhetoric beyond layout grids."""

from __future__ import annotations

from archium.domain.visual.visual_language.color_story import (
    NAMED_SWATCHES,
    ColorRole,
    ColorStory,
)
from archium.domain.visual.visual_language.decoration import (
    CardStyle,
    DecorationId,
    DecorationRecipe,
    DividerKind,
)
from archium.domain.visual.visual_language.layering import SceneLayerRole
from archium.domain.visual.visual_language.spec import ImageBehavior, VisualLanguageSpec
from archium.domain.visual.visual_language.symbols import (
    SYMBOL_GLYPHS,
    ArchitecturalSymbolId,
)
from archium.domain.visual.visual_language.typography import (
    TitleCase,
    TitleDecoration,
    TitleScale,
    Tracking,
    TypographyRecipe,
    TypographyRecipeId,
)

__all__ = [
    "ArchitecturalSymbolId",
    "CardStyle",
    "ColorRole",
    "ColorStory",
    "DecorationId",
    "DecorationRecipe",
    "DividerKind",
    "ImageBehavior",
    "NAMED_SWATCHES",
    "SYMBOL_GLYPHS",
    "SceneLayerRole",
    "TitleCase",
    "TitleDecoration",
    "TitleScale",
    "Tracking",
    "TypographyRecipe",
    "TypographyRecipeId",
    "VisualLanguageSpec",
]
