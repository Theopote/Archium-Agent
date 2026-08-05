"""Architectural presentation visual language — rhetoric beyond layout grids."""

from __future__ import annotations

from archium.domain.visual.visual_language.atmosphere import (
    AtmosphereKind,
    AtmosphereSpec,
)
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
from archium.domain.visual.visual_language.image_composition import (
    AnalysisLineKind,
    ImageCompositionMode,
    ImageCompositionPlan,
    ImageSlotRole,
)
from archium.domain.visual.visual_language.image_mask import ImageMaskKind, ImageMaskSpec
from archium.domain.visual.visual_language.layering import SceneLayerRole
from archium.domain.visual.visual_language.spec import ImageBehavior, VisualLanguageSpec
from archium.domain.visual.visual_language.symbols import (
    SYMBOL_GLYPHS,
    ArchitecturalSymbolId,
)
from archium.domain.visual.visual_language.typography import (
    ROLE_CATALOG,
    TitleCase,
    TitleDecoration,
    TitleScale,
    Tracking,
    TypographyPosition,
    TypographyRecipe,
    TypographyRecipeId,
    TypographyRole,
    TypographyRoleSpec,
    primary_role_for_recipe,
    role_spec,
)
from archium.domain.visual.visual_language.typography_composition import (
    TypographyArrangement,
    TypographyComposition,
    TypographyPageKind,
    TypographyRunRole,
    TypographyRunSpec,
)

__all__ = [
    "AnalysisLineKind",
    "ArchitecturalSymbolId",
    "AtmosphereKind",
    "AtmosphereSpec",
    "CardStyle",
    "ColorRole",
    "ColorStory",
    "DecorationId",
    "DecorationRecipe",
    "DividerKind",
    "ImageBehavior",
    "ImageCompositionMode",
    "ImageCompositionPlan",
    "ImageMaskKind",
    "ImageMaskSpec",
    "ImageSlotRole",
    "NAMED_SWATCHES",
    "ROLE_CATALOG",
    "SYMBOL_GLYPHS",
    "SceneLayerRole",
    "TitleCase",
    "TitleDecoration",
    "TitleScale",
    "Tracking",
    "TypographyArrangement",
    "TypographyComposition",
    "TypographyPageKind",
    "TypographyPosition",
    "TypographyRecipe",
    "TypographyRecipeId",
    "TypographyRole",
    "TypographyRoleSpec",
    "TypographyRunRole",
    "TypographyRunSpec",
    "VisualLanguageSpec",
    "primary_role_for_recipe",
    "role_spec",
]
