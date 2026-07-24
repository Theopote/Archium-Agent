"""Resolve theme stroke color for bundled architectural icons."""

from __future__ import annotations

from archium.domain.visual.design_system import DesignSystem

ICON_STROKE_TOKEN = "accent"


def resolve_icon_stroke_token() -> str:
    return ICON_STROKE_TOKEN


def resolve_icon_stroke_color(design_system: DesignSystem) -> str:
    """Map decorative icon strokes to the presentation accent color."""
    return design_system.colors.resolve(resolve_icon_stroke_token())
