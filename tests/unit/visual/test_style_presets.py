"""Unit tests for Architecture Style Preset system (v0.3 Showcase Phase 1.1)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.layout_style_preference import derive_layout_style_preference
from archium.application.visual.style_overlay import apply_style_overlays
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import DensityLevel, LayoutFamily
from archium.domain.visual.style import (
    DEFAULT_STYLE_PRESET_ID,
    StylePresetId,
    apply_style_preset,
    design_system_fingerprint,
    get_style_preset,
    list_style_presets,
    resolve_style_preset_id,
)
from archium.infrastructure.layout.generators.base import (
    LayoutContentBundle,
    LayoutGeneratorContext,
)
from archium.infrastructure.layout.generators.hero import HeroLayoutGenerator
from archium.domain.slide import SlideSpec
from archium.domain.visual.visual_intent import VisualIntent
from archium.domain.visual.enums import VisualContentType


def _minimal_art(**kwargs: object) -> ArtDirection:
    defaults: dict[str, object] = {
        "project_id": uuid4(),
        "concept_name": "test",
        "rationale": "unit test art direction",
        "palette_strategy": "neutral",
        "typography_strategy": "readable",
        "grid_strategy": "12 column",
        "image_strategy": "contain",
        "drawing_strategy": "contain",
        "diagram_strategy": "sparse",
        "annotation_strategy": "minimal",
        "cover_strategy": "hero",
        "section_strategy": "spacious",
        "content_strategy": "balanced",
        "closing_strategy": "summary",
        "pacing_strategy": "steady",
    }
    defaults.update(kwargs)
    return ArtDirection(**defaults)  # type: ignore[arg-type]


def test_registry_has_six_presets() -> None:
    presets = list_style_presets()
    assert len(presets) == 6
    assert {p.id for p in presets} == set(StylePresetId)
    assert DEFAULT_STYLE_PRESET_ID == StylePresetId.ARCHITECTURE_TECHNICAL


def test_unknown_preset_raises() -> None:
    with pytest.raises(KeyError):
        get_style_preset("not_a_real_preset")
    with pytest.raises(KeyError):
        resolve_style_preset_id("som_clone_v99")


def test_minimal_vs_technical_measurable_token_diff() -> None:
    base = default_presentation_design_system()
    minimal = apply_style_preset(base, get_style_preset(StylePresetId.ARCHITECTURE_MINIMAL))
    technical = apply_style_preset(base, get_style_preset(StylePresetId.ARCHITECTURE_TECHNICAL))

    assert minimal.page.margin_left > technical.page.margin_left
    assert minimal.grid.gutter > technical.grid.gutter
    assert minimal.typography.body.font_size == 15.0
    assert technical.typography.body.font_size == 14.0
    assert minimal.thresholds.min_hero_area_ratio > technical.thresholds.min_hero_area_ratio
    assert minimal.thresholds.min_whitespace_ratio > technical.thresholds.min_whitespace_ratio
    assert design_system_fingerprint(minimal) != design_system_fingerprint(technical)
    # Base unchanged
    assert base.page.margin_left == 0.7
    assert base.typography.body.font_size == 16


def test_style_overlay_applies_preset_from_art_direction() -> None:
    base = default_presentation_design_system()
    art = _minimal_art(style_preset_id=StylePresetId.ARCHITECTURE_MINIMAL.value)
    result = apply_style_overlays(base, art_direction=art)
    assert result.design_system.thresholds.min_hero_area_ratio == 0.52
    assert any("style_preset=architecture_minimal" in w for w in result.warnings)
    assert base.thresholds.min_hero_area_ratio != result.design_system.thresholds.min_hero_area_ratio


def test_layout_style_preference_reads_preset() -> None:
    art = _minimal_art(style_preset_id=StylePresetId.ARCHITECTURE_MINIMAL.value)
    pref = derive_layout_style_preference(art_direction=art)
    assert LayoutFamily.HERO in pref.preferred_families
    assert any("style_preset=architecture_minimal" in n for n in pref.notes)
    # Metric dashboard is soft-demoted for minimal; should not be top family.
    if LayoutFamily.METRIC_DASHBOARD in pref.preferred_families:
        assert pref.family_rank(LayoutFamily.HERO) is not None
        assert pref.family_rank(LayoutFamily.HERO) < pref.family_rank(
            LayoutFamily.METRIC_DASHBOARD
        )


def test_hero_safe_area_differs_by_preset() -> None:
    """Same SlideSpec + Hero generator: minimal has smaller content box than technical."""
    base = default_presentation_design_system()
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="open",
        order=0,
        title="项目愿景",
        message="以院落重构公共空间。",
    )
    intent = VisualIntent(
        slide_id=slide.id,
        communication_goal="建立第一印象",
        audience_takeaway="院落是核心",
        visual_priority="hero",
        dominant_content_type=VisualContentType.HERO_IMAGE,
        preferred_layout_families=[LayoutFamily.HERO],
        density_level=DensityLevel.BALANCED,
    )
    content = LayoutContentBundle(
        title=slide.title,
        message=slide.message,
        key_points=[],
        hero_asset_ref=None,
    )

    plans = {}
    for preset_id in (
        StylePresetId.ARCHITECTURE_MINIMAL,
        StylePresetId.ARCHITECTURE_TECHNICAL,
    ):
        design = apply_style_preset(base, get_style_preset(preset_id))
        ctx = LayoutGeneratorContext(
            slide=slide,
            visual_intent=intent,
            art_direction=None,
            design_system=design,
            content=content,
            variant="full_bleed",
        )
        plans[preset_id] = HeroLayoutGenerator().generate(ctx)

    min_hero = next(el for el in plans[StylePresetId.ARCHITECTURE_MINIMAL].elements if el.id == "hero")
    tech_hero = next(
        el for el in plans[StylePresetId.ARCHITECTURE_TECHNICAL].elements if el.id == "hero"
    )
    # Larger margins → smaller hero box area for minimal.
    min_area = min_hero.width * min_hero.height
    tech_area = tech_hero.width * tech_hero.height
    assert min_area < tech_area
