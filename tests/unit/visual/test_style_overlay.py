"""Unit tests for ArtDirection / ReferenceStyle → DesignSystem overlays."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.style_overlay import apply_style_overlays, extract_hex_colors
from archium.domain.reference_style import (
    ReferenceStyleProfile,
    StyleColorCue,
    StyleTypographyCue,
)
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.defaults import default_presentation_design_system


def test_extract_hex_colors_normalizes() -> None:
    assert extract_hex_colors("bg #ff00aa and border #ABC") == ["#FF00AA", "#AABBCC"]


def test_reference_style_color_and_typography_overlay() -> None:
    design = default_presentation_design_system()
    profile = ReferenceStyleProfile(
        project_id=uuid4(),
        style_name="ref",
        color_cues=[
            StyleColorCue(
                id="accent",
                name="brand",
                description="Accent color #112233 for highlights",
                usage="accent",
            )
        ],
        typography_cues=[
            StyleTypographyCue(
                id="body",
                role="body",
                description='font_family: "Georgia" body at 18pt',
            )
        ],
    )
    result = apply_style_overlays(design, reference_style=profile)
    assert result.design_system.colors.accent.upper() == "#112233"
    assert result.design_system.typography.body.font_size == 18.0
    assert "Georgia" in result.design_system.typography.body.font_family
    assert "accent" in result.applied_color_tokens
    assert "body" in result.applied_typography_roles
    # Original design system not mutated.
    assert design.colors.accent != result.design_system.colors.accent


def test_art_direction_dark_and_oversized() -> None:
    design = default_presentation_design_system()
    art = ArtDirection(
        project_id=uuid4(),
        concept_name="dark",
        rationale="dark mode for night review",
        palette_strategy="dark night board",
        typography_strategy="oversized display titles",
        grid_strategy="standard",
        image_strategy="contain",
        drawing_strategy="clean",
        diagram_strategy="simple",
        annotation_strategy="minimal",
        cover_strategy="hero",
        section_strategy="divider",
        content_strategy="balanced",
        closing_strategy="summary",
        pacing_strategy="steady",
        visual_tone=["dark"],
    )
    result = apply_style_overlays(design, art_direction=art)
    assert result.design_system.colors.background.upper() == "#1A1A1A"
    assert result.design_system.typography.title.font_size > design.typography.title.font_size
    assert any("dark_palette" in note for note in result.warnings)


def test_reference_style_wins_over_art_direction_on_same_token() -> None:
    design = default_presentation_design_system()
    project_id = uuid4()
    art = ArtDirection(
        project_id=project_id,
        concept_name="warm",
        rationale="warm accent",
        palette_strategy="warm terracotta",
        typography_strategy="balanced",
        grid_strategy="standard",
        image_strategy="contain",
        drawing_strategy="clean",
        diagram_strategy="simple",
        annotation_strategy="minimal",
        cover_strategy="hero",
        section_strategy="divider",
        content_strategy="balanced",
        closing_strategy="summary",
        pacing_strategy="steady",
    )
    profile = ReferenceStyleProfile(
        project_id=project_id,
        style_name="ref-accent",
        color_cues=[
            StyleColorCue(
                id="a",
                name="accent",
                description="#00FF99 accent",
                usage="accent",
            )
        ],
    )
    result = apply_style_overlays(design, art_direction=art, reference_style=profile)
    assert result.design_system.colors.accent.upper() == "#00FF99"
