"""Design token bridge from DesignSystem to pptxgen theme-like dicts."""

from __future__ import annotations

from typing import Any

from archium.domain.visual.design_system import DesignSystem


def design_system_to_pptx_theme(design_system: DesignSystem) -> dict[str, Any]:
    """Map DesignSystem tokens into a structure compatible with theme.mjs fields."""
    colors = design_system.colors
    typography = design_system.typography
    page = design_system.page
    return {
        "name": design_system.name,
        "fonts": {
            "heading": typography.title.font_family,
            "body": typography.body.font_family,
            "caption": typography.caption.font_family,
        },
        "colors": {
            "primary": colors.primary.lstrip("#"),
            "accent": colors.accent.lstrip("#"),
            "text": colors.primary_text.lstrip("#"),
            "muted": colors.muted_text.lstrip("#"),
            "light": colors.surface.lstrip("#"),
            "white": colors.background.lstrip("#"),
            "onPrimary": colors.background.lstrip("#"),
            "subtitle": colors.secondary_text.lstrip("#"),
        },
        "spacing": {
            "marginX": page.margin_left,
            "marginY": page.margin_top,
            "gutter": design_system.grid.gutter,
            "headerHeight": typography.title.font_size / 72.0 + design_system.spacing.sm,
        },
        "slide_size": {
            "width": page.width,
            "height": page.height,
            "layout": "LAYOUT_16x9" if abs(page.width / page.height - 16 / 9) < 0.05 else "CUSTOM",
        },
        "component_styles": {
            "title": {"fontSize": typography.title.font_size, "bold": True},
            "section": {"fontSize": typography.display.font_size, "bold": True},
            "header": {"fontSize": typography.heading.font_size, "bold": True},
            "body": {"fontSize": typography.body.font_size},
            "caption": {"fontSize": typography.caption.font_size},
            "metric": {"fontSize": typography.metric.font_size, "bold": True},
        },
    }
