"""ArtDirectionProfile — office aesthetic traits derived from StylePreset.

Bridges StylePreset tokens to VisualLanguage knobs (typography, budget,
decoration, color). Distinct from persisted ArtDirection prose strategies.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import DensityLevel
from archium.domain.visual.style.presets import StylePreset, StylePresetId
from archium.domain.visual.visual_budget import VisualBudget
from archium.domain.visual.visual_language import (
    CardStyle,
    ColorStory,
    DecorationRecipe,
    ImageMaskKind,
    ImageMaskSpec,
    TitleDecoration,
    TitleScale,
    Tracking,
    TypographyRecipe,
    VisualLanguageSpec,
)

_AVOID_TAG_MAP: dict[str, str] = {
    "icon_overload": "icon_overload",
    "metric_dashboard_heavy": "metric_dashboard",
    "loud_accent": "loud_accent",
    "decorative_frame": "decorative_frames",
    "tourism_brochure": "tourism_brochure",
    "dense_caption_wall": "dense_caption",
}


class ArtDirectionTrait(StrEnum):
    """Executable visual traits an office aesthetic encourages."""

    LARGE_WHITESPACE = "large_whitespace"
    THIN_LINES = "thin_lines"
    MONOCHROME = "monochrome"
    PRECISE_ANNOTATION = "precise_annotation"
    STRONG_TITLES = "strong_titles"
    PHOTO_DOMINANT = "photo_dominant"
    DENSE_DRAWINGS = "dense_drawings"
    WARNING_ACCENT = "warning_accent"
    SOFT_ATMOSPHERE = "soft_atmosphere"
    QUIET_TITLES = "quiet_titles"


class ArtDirectionAvoid(StrEnum):
    """Elements the profile actively suppresses."""

    CARDS = "cards"
    GRADIENTS = "gradients"
    ICON_OVERLOAD = "icon_overload"
    METRIC_DASHBOARD = "metric_dashboard"
    LOUD_ACCENT = "loud_accent"
    DECORATIVE_FRAMES = "decorative_frames"
    TOURISM_BROCHURE = "tourism_brochure"
    DENSE_CAPTION = "dense_caption"


class ArtDirectionProfile(DomainModel):
    """Office-level art direction — traits + avoid, bound to a StylePreset."""

    name: str = Field(min_length=1, max_length=80)
    reference: str = Field(default="", max_length=120)
    style_preset_id: str = Field(min_length=1)
    traits: tuple[ArtDirectionTrait, ...] = ()
    avoid: tuple[ArtDirectionAvoid, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "reference": self.reference,
            "style_preset_id": self.style_preset_id,
            "traits": [t.value for t in self.traits],
            "avoid": [a.value for a in self.avoid],
        }


def profile_for_style_preset(preset: StylePreset) -> ArtDirectionProfile:
    """Derive an ArtDirectionProfile from a StylePreset definition."""
    traits: list[ArtDirectionTrait] = []
    avoid: list[ArtDirectionAvoid] = []

    ws = preset.content_policy.preferred_whitespace
    if preset.density == DensityLevel.SPACIOUS or (ws is not None and ws >= 0.25):
        traits.append(ArtDirectionTrait.LARGE_WHITESPACE)
    if preset.density == DensityLevel.COMPACT:
        traits.append(ArtDirectionTrait.DENSE_DRAWINGS)
    if preset.title_style in {"quiet_bar", "soft_bar"}:
        traits.extend([ArtDirectionTrait.THIN_LINES, ArtDirectionTrait.QUIET_TITLES])
    elif preset.title_style in {"strong_bar", "problem_bar"}:
        traits.append(ArtDirectionTrait.STRONG_TITLES)
    if preset.max_accent_ratio <= 0.05:
        traits.append(ArtDirectionTrait.MONOCHROME)
    if preset.presentation_personality.image_role.value == "dominant":
        traits.append(ArtDirectionTrait.PHOTO_DOMINANT)
    if preset.id == StylePresetId.ARCHITECTURE_URBAN:
        traits.append(ArtDirectionTrait.WARNING_ACCENT)
    if preset.id == StylePresetId.ARCHITECTURE_LANDSCAPE:
        traits.append(ArtDirectionTrait.SOFT_ATMOSPHERE)
    if preset.diagram_style in {"line_sparse", "annotated_figure"}:
        traits.append(ArtDirectionTrait.PRECISE_ANNOTATION)

    for tag in preset.forbidden_style_tags:
        mapped = _AVOID_TAG_MAP.get(tag)
        if mapped:
            try:
                avoid.append(ArtDirectionAvoid(mapped))
            except ValueError:
                pass
    avoid.extend(_cards_avoid_for_preset(preset))

    references = {
        StylePresetId.ARCHITECTURE_MINIMAL: "SOM + SANAA",
        StylePresetId.ARCHITECTURE_TECHNICAL: "Design Institute Board",
        StylePresetId.ARCHITECTURE_LUXURY: "MAD + Herzog de Meuron",
        StylePresetId.ARCHITECTURE_ACADEMIC: "Campus Research Report",
        StylePresetId.ARCHITECTURE_URBAN: "Urban Renewal Competition",
        StylePresetId.ARCHITECTURE_LANDSCAPE: "Landscape Atelier",
    }
    return ArtDirectionProfile(
        name=preset.display_name,
        reference=references.get(preset.id, ""),
        style_preset_id=preset.id.value,
        traits=tuple(dict.fromkeys(traits)),
        avoid=tuple(dict.fromkeys(avoid)),
    )


def _cards_avoid_for_preset(preset: StylePreset) -> list[ArtDirectionAvoid]:
    """Minimal and luxury presets suppress card-heavy strategy pages."""
    if preset.id in {
        StylePresetId.ARCHITECTURE_MINIMAL,
        StylePresetId.ARCHITECTURE_LUXURY,
        StylePresetId.ARCHITECTURE_LANDSCAPE,
    }:
        return [ArtDirectionAvoid.CARDS]
    return []


def apply_profile_to_typography_and_budget(
    typography: TypographyRecipe,
    budget: VisualBudget,
    profile: ArtDirectionProfile,
) -> tuple[TypographyRecipe, VisualBudget]:
    """Adjust typography + budget caps from art-direction traits."""
    typo = typography
    b = budget

    if ArtDirectionTrait.STRONG_TITLES in profile.traits:
        scale = TitleScale.LARGE if typo.scale == TitleScale.NORMAL else typo.scale
        size = typo.title_font_size_pt
        typo = typo.model_copy(
            update={
                "scale": scale,
                "title_font_size_pt": (size * 1.08) if size else size,
                "tracking": Tracking.WIDE,
            }
        )
    if ArtDirectionTrait.QUIET_TITLES in profile.traits:
        size = typo.title_font_size_pt
        typo = typo.model_copy(
            update={
                "scale": TitleScale.NORMAL,
                "title_font_size_pt": (size * 0.92) if size else size,
                "opacity": min(typo.opacity, 0.88),
            }
        )
    if ArtDirectionTrait.THIN_LINES in profile.traits:
        typo = typo.model_copy(update={"decoration": TitleDecoration.THIN_LINE})

    hero = b.hero_ratio
    lines = b.decorative_lines
    icons = b.icons
    blocks = b.color_blocks

    if ArtDirectionTrait.LARGE_WHITESPACE in profile.traits:
        hero = min(0.78, hero + 0.06)
        lines = max(0, lines - 1)
        icons = max(0, icons - 1)
    if ArtDirectionTrait.PHOTO_DOMINANT in profile.traits:
        hero = min(0.82, max(hero, 0.58))
    if ArtDirectionTrait.DENSE_DRAWINGS in profile.traits:
        lines = min(lines + 1, 6)
    if ArtDirectionAvoid.ICON_OVERLOAD in profile.avoid:
        icons = min(icons, 1)
    if ArtDirectionAvoid.LOUD_ACCENT in profile.avoid:
        blocks = min(blocks, 1)

    b = b.model_copy(
        update={
            "hero_ratio": hero,
            "decorative_lines": lines,
            "icons": icons,
            "color_blocks": blocks,
        }
    )
    return typo, b


def apply_profile_to_color_story(
    color_story: ColorStory,
    profile: ArtDirectionProfile,
) -> ColorStory:
    """Monochrome profiles simplify palette to greyscale roles."""
    if ArtDirectionTrait.MONOCHROME not in profile.traits:
        return color_story
    if not color_story.roles:
        return ColorStory(
            roles={
                "neutral": "gray",
                "accent": "dark_gray",
            },
            meaning={"gray": "structure", "dark_gray": "emphasis"},
            source="ad_profile:monochrome",
        )
    muted: dict[str, str] = {}
    greys = ("gray", "dark_gray", "light_gray", "charcoal")
    for index, (role, _swatch) in enumerate(color_story.roles.items()):
        muted[role] = greys[index % len(greys)]
    return ColorStory(
        roles=muted,
        meaning={v: k for k, v in muted.items()},
        source="ad_profile:mono",
    )


def apply_profile_to_decoration(
    decoration: DecorationRecipe,
    profile: ArtDirectionProfile,
) -> DecorationRecipe:
    """Suppress card-heavy decoration when profile avoids cards."""
    if ArtDirectionAvoid.CARDS not in profile.avoid:
        return decoration
    return decoration.model_copy(update={"card_style": CardStyle.NONE})


def apply_profile_to_language(
    language: VisualLanguageSpec,
    budget: VisualBudget,
    profile: ArtDirectionProfile,
) -> tuple[VisualLanguageSpec, VisualBudget]:
    """Full profile pass — typography, color, decoration, mask, budget."""
    typo, budget = apply_profile_to_typography_and_budget(
        language.typography, budget, profile
    )
    color = apply_profile_to_color_story(language.color_story, profile)
    deco = apply_profile_to_decoration(language.decoration, profile)
    mask = language.image_mask
    if ArtDirectionAvoid.GRADIENTS in profile.avoid and mask.kind == ImageMaskKind.GRADIENT_FADE:
        mask = ImageMaskSpec(
            kind=ImageMaskKind.ROUNDED,
            corner_radius=mask.corner_radius,
            edge_softness=mask.edge_softness,
            source="ad_profile:no_gradient",
        )
    updated = language.model_copy(
        update={
            "typography": typo,
            "color_story": color,
            "decoration": deco,
            "image_mask": mask,
            "source": f"ad:{profile.style_preset_id}",
        }
    )
    return updated, budget
