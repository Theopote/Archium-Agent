"""Unit tests for DeckThemeTokens → DesignSystem mapping."""

from __future__ import annotations

from archium.application.visual.deck_theme_apply import apply_tokens_to_design_system
from archium.domain.visual.deck_theme_tokens import DeckThemeTokens
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import ImageFit, PhotoTreatment


def test_apply_colors_and_fonts() -> None:
    base = default_presentation_design_system()
    tokens = DeckThemeTokens(
        primary="#112233",
        accent="#AABBCC",
        background="#FEFEFE",
        title_font="SimSun",
        body_font="SimHei",
    )
    proposed = apply_tokens_to_design_system(base, tokens)
    assert proposed.id != base.id
    assert proposed.version == base.version + 1
    assert proposed.colors.primary == "#112233"
    assert proposed.colors.accent == "#AABBCC"
    assert proposed.colors.background == "#FEFEFE"
    assert proposed.typography.title.font_family == "SimSun"
    assert proposed.typography.heading.font_family == "SimSun"
    assert proposed.typography.body.font_family == "SimHei"
    assert proposed.typography.caption.font_family == "SimHei"
    # Base unchanged
    assert base.colors.primary != "#112233"


def test_title_scale_and_density() -> None:
    base = default_presentation_design_system()
    before_title = base.typography.title.font_size
    before_md = base.spacing.md
    proposed = apply_tokens_to_design_system(
        base,
        DeckThemeTokens(title_scale=1.2, page_density="dense"),
    )
    assert proposed.typography.title.font_size == round(before_title * 1.2, 2)
    assert proposed.spacing.md == before_md * 0.85


def test_photo_treatment_does_not_force_drawing_cover() -> None:
    base = default_presentation_design_system()
    assert base.image_style.default_fit == ImageFit.CONTAIN
    proposed = apply_tokens_to_design_system(
        base,
        DeckThemeTokens(
            photo_treatment=PhotoTreatment.HISTORICAL,
            corner_radius=0.1,
            line_weight=1.2,
            icon_style="minimal",
        ),
    )
    assert proposed.image_style.photo_treatment == PhotoTreatment.HISTORICAL
    assert proposed.image_style.default_fit == ImageFit.CONTAIN
    assert proposed.image_style.default_corner_radius == 0.1
    assert proposed.annotation_style.line_weight == 1.2
    assert proposed.annotation_style.marker_size == 0.16
