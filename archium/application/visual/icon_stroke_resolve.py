"""Shim: icon stroke resolve lives in domain.visual."""

from archium.domain.visual.icon_stroke_resolve import (
    ICON_STROKE_TOKEN,
    resolve_icon_stroke_color,
    resolve_icon_stroke_token,
)

__all__ = [
    "ICON_STROKE_TOKEN",
    "resolve_icon_stroke_color",
    "resolve_icon_stroke_token",
]
