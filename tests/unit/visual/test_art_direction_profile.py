"""ArtDirectionProfile — StylePreset → visual language traits."""

from __future__ import annotations

from archium.application.visual.showcase_case_001 import build_case_001_render_bundle
from archium.application.visual.visual_language_service import VisualLanguageService
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction_profile import (
    ArtDirectionAvoid,
    ArtDirectionTrait,
    apply_profile_to_language,
    profile_for_style_preset,
)
from archium.domain.visual.page_direction import NarrativeEmotion, PageDirection
from archium.domain.visual.style import get_style_preset, list_style_presets
from archium.domain.visual.style.presets import StylePresetId
from archium.domain.visual.visual_budget import VisualBudget
from archium.domain.visual.visual_language import (
    CardStyle,
    TypographyRecipe,
    VisualLanguageSpec,
)


def test_every_style_preset_has_art_direction_profile() -> None:
    for preset in list_style_presets():
        profile = profile_for_style_preset(preset)
        assert profile.name == preset.display_name
        assert profile.style_preset_id == preset.id.value
        assert isinstance(profile.traits, tuple)
        assert isinstance(profile.avoid, tuple)


def test_minimal_preset_traits_and_avoid() -> None:
    preset = get_style_preset(StylePresetId.ARCHITECTURE_MINIMAL)
    profile = profile_for_style_preset(preset)
    assert ArtDirectionTrait.LARGE_WHITESPACE in profile.traits
    assert ArtDirectionTrait.THIN_LINES in profile.traits
    assert ArtDirectionTrait.MONOCHROME in profile.traits
    assert ArtDirectionTrait.QUIET_TITLES in profile.traits
    assert ArtDirectionAvoid.CARDS in profile.avoid
    assert profile.reference == "SOM + SANAA"


def test_urban_preset_has_warning_accent() -> None:
    preset = get_style_preset(StylePresetId.ARCHITECTURE_URBAN)
    profile = profile_for_style_preset(preset)
    assert ArtDirectionTrait.WARNING_ACCENT in profile.traits
    assert ArtDirectionTrait.DENSE_DRAWINGS in profile.traits


def test_profile_reduces_icons_when_avoiding_overload() -> None:
    preset = get_style_preset(StylePresetId.ARCHITECTURE_MINIMAL)
    profile = profile_for_style_preset(preset)
    spec = VisualLanguageSpec(typography=TypographyRecipe())
    budget = VisualBudget(icons=3, decorative_lines=3)
    _, updated = apply_profile_to_language(spec, budget, profile)
    assert updated.icons <= 1


def test_profile_suppresses_cards_on_strategy_decoration() -> None:
    from archium.domain.visual.visual_language import DecorationRecipe

    preset = get_style_preset(StylePresetId.ARCHITECTURE_MINIMAL)
    profile = profile_for_style_preset(preset)
    deco = DecorationRecipe(card_style=CardStyle.TECHNICAL)
    from archium.domain.visual.art_direction_profile import apply_profile_to_decoration

    result = apply_profile_to_decoration(deco, profile)
    assert result.card_style == CardStyle.NONE


def test_visual_language_compose_applies_style_preset() -> None:
    from uuid import uuid4

    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="demo",
        title="封面",
        message="医院更新",
        order=1,
    )
    direction = PageDirection(
        single_message="医院更新",
        narrative_emotion=NarrativeEmotion.CLIMAX,
    )
    preset = get_style_preset(StylePresetId.ARCHITECTURE_MINIMAL)
    svc = VisualLanguageService()
    spec = svc.compose(slide, direction, style_preset=preset)
    assert spec.source.startswith("ad:architecture_minimal")


def test_case_001_cover_uses_art_direction_source() -> None:
    bundle = build_case_001_render_bundle()
    cover_idx = next(i for i, s in enumerate(bundle.slides) if s.title == "封面")
    direction = bundle.intents[cover_idx].page_direction
    assert direction is not None
    assert direction.visual_language is not None
    assert direction.visual_language.source.startswith("ad:")
