"""Shim: SVG icon recolor lives in infrastructure.renderers."""

from archium.infrastructure.renderers.svg_icon_recolor import (
    PACK_DEFAULT_STROKE,
    is_architectural_icon_ref,
    materialize_recolored_icon,
    normalize_icon_stroke_color,
    recolor_icon_svg_text,
)

__all__ = [
    "PACK_DEFAULT_STROKE",
    "is_architectural_icon_ref",
    "materialize_recolored_icon",
    "normalize_icon_stroke_color",
    "recolor_icon_svg_text",
]
