"""Apply StylePreset → in-memory DesignSystem token overrides."""

from __future__ import annotations

import hashlib
import json

from archium.domain.visual.design_system import (
    ColorSystem,
    DesignSystem,
    GridSystem,
    LayoutThresholds,
    PageSystem,
    SpacingSystem,
    TextStyleToken,
    TypographySystem,
)
from archium.domain.visual.style.presets import StylePreset

_COLOR_KEYS = (
    "background",
    "surface",
    "primary_text",
    "secondary_text",
    "muted_text",
    "primary",
    "secondary",
    "accent",
    "warning",
    "success",
    "border",
    "overlay",
)


def apply_style_preset(base: DesignSystem, preset: StylePreset) -> DesignSystem:
    """Return a copy of ``base`` with measurable StylePreset overrides applied.

    Persisted DesignSystem rows are not mutated. Callers use the result for
    layout generation, validation thresholds, and RenderScene compilation.
    """
    page = _scale_page(base.page, preset.margin_scale)
    grid = _scale_grid(base.grid, preset.gutter_scale)
    spacing = _scale_spacing(base.spacing, preset.spacing_scale)
    typography = _scale_typography(base.typography, preset)
    colors = _merge_colors(base.colors, preset.colors)
    thresholds = _merge_thresholds(base.thresholds, preset)

    return base.model_copy(
        update={
            "name": f"{base.name}+{preset.id.value}",
            "description": (
                f"{base.description} [style_preset:{preset.id.value}]"
            ).strip(),
            "page": page,
            "grid": grid,
            "spacing": spacing,
            "typography": typography,
            "colors": colors,
            "thresholds": thresholds,
            "source_reference": (
                f"{base.source_reference or 'design_system'}"
                f"|style_preset:{preset.id.value}"
            ),
        }
    )


def design_system_fingerprint(design: DesignSystem) -> str:
    """Stable short hash of measurable tokens (for golden / compare tests)."""
    payload = {
        "margins": [
            design.page.margin_top,
            design.page.margin_right,
            design.page.margin_bottom,
            design.page.margin_left,
        ],
        "gutter": design.grid.gutter,
        "body_pt": design.typography.body.font_size,
        "title_pt": design.typography.title.font_size,
        "hero_min": design.thresholds.min_hero_area_ratio,
        "ws_min": design.thresholds.min_whitespace_ratio,
        "ws_max": design.thresholds.max_whitespace_ratio,
        "accent": design.colors.accent,
        "background": design.colors.background,
        "source": design.source_reference,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _scale_page(page: PageSystem, margin_scale: float) -> PageSystem:
    if abs(margin_scale - 1.0) < 1e-9:
        return page
    return page.model_copy(
        update={
            "margin_top": round(page.margin_top * margin_scale, 4),
            "margin_right": round(page.margin_right * margin_scale, 4),
            "margin_bottom": round(page.margin_bottom * margin_scale, 4),
            "margin_left": round(page.margin_left * margin_scale, 4),
        }
    )


def _scale_grid(grid: GridSystem, gutter_scale: float) -> GridSystem:
    if abs(gutter_scale - 1.0) < 1e-9:
        return grid
    updates: dict[str, float] = {"gutter": round(grid.gutter * gutter_scale, 4)}
    if grid.row_gutter is not None:
        updates["row_gutter"] = round(grid.row_gutter * gutter_scale, 4)
    return grid.model_copy(update=updates)


def _scale_spacing(spacing: SpacingSystem, spacing_scale: float) -> SpacingSystem:
    if abs(spacing_scale - 1.0) < 1e-9:
        return spacing
    return SpacingSystem(
        xs=round(spacing.xs * spacing_scale, 5),
        sm=round(spacing.sm * spacing_scale, 5),
        md=round(spacing.md * spacing_scale, 5),
        lg=round(spacing.lg * spacing_scale, 5),
        xl=round(spacing.xl * spacing_scale, 5),
        xxl=round(spacing.xxl * spacing_scale, 5),
    )


def _scale_token(
    token: TextStyleToken,
    *,
    size_scale: float = 1.0,
    absolute_size: float | None = None,
    letter_spacing_bias: float = 0.0,
) -> TextStyleToken:
    size = absolute_size if absolute_size is not None else round(token.font_size * size_scale, 2)
    line = round(size * (token.line_height / token.font_size), 2) if token.font_size else token.line_height
    return token.model_copy(
        update={
            "font_size": size,
            "line_height": line,
            "letter_spacing": round(token.letter_spacing + letter_spacing_bias, 3),
        }
    )


def _scale_typography(base: TypographySystem, preset: StylePreset) -> TypographySystem:
    title_scale = preset.title_scale
    body_pt = preset.body_pt
    bias = preset.letter_spacing_bias
    return TypographySystem(
        display=_scale_token(base.display, size_scale=title_scale, letter_spacing_bias=bias),
        title=_scale_token(base.title, size_scale=title_scale, letter_spacing_bias=bias),
        subtitle=_scale_token(base.subtitle, size_scale=1.0 + (title_scale - 1.0) * 0.4),
        heading=_scale_token(base.heading, size_scale=1.0 + (title_scale - 1.0) * 0.5),
        body=_scale_token(base.body, absolute_size=body_pt) if body_pt else base.body,
        caption=base.caption,
        metric=base.metric,
        footnote=base.footnote,
        source=base.source,
    )


def _merge_colors(base: ColorSystem, overrides: dict[str, str]) -> ColorSystem:
    if not overrides:
        return base
    updates: dict[str, str] = {}
    for key, value in overrides.items():
        if key in _COLOR_KEYS:
            updates[key] = value
    if not updates:
        return base
    return base.model_copy(update=updates)


def _merge_thresholds(base: LayoutThresholds, preset: StylePreset) -> LayoutThresholds:
    updates: dict[str, float] = {}
    if preset.hero_min_area_ratio is not None:
        updates["min_hero_area_ratio"] = preset.hero_min_area_ratio
    if preset.min_whitespace_ratio is not None:
        updates["min_whitespace_ratio"] = preset.min_whitespace_ratio
    if preset.max_whitespace_ratio is not None:
        updates["max_whitespace_ratio"] = preset.max_whitespace_ratio
    if preset.body_pt is not None:
        # Keep body floor aligned with preset body size (slightly below).
        updates["min_body_font_pt"] = max(10.0, round(preset.body_pt - 1.0, 1))
    if not updates:
        return base
    return base.model_copy(update=updates)
