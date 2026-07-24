"""Shim: text style resolve lives in domain.visual."""

from archium.domain.visual.text_style_resolve import (
    TYPOGRAPHY_TOKEN_NAMES,
    base_text_style,
    clamp_font_size_override,
    effective_font_size,
    next_larger_token,
    resolve_text_style,
    role_min_font_pt,
    smaller_compliant_tokens,
    typography_tokens_by_size,
)

__all__ = [
    "TYPOGRAPHY_TOKEN_NAMES",
    "base_text_style",
    "clamp_font_size_override",
    "effective_font_size",
    "next_larger_token",
    "resolve_text_style",
    "role_min_font_pt",
    "smaller_compliant_tokens",
    "typography_tokens_by_size",
]
