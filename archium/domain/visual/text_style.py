"""Resolve effective text styles from DesignSystem typography + element overrides."""

from __future__ import annotations

from archium.domain.visual.design_system import (
    LayoutThresholds,
    TextStyleToken,
    TypographySystem,
)
from archium.domain.visual.enums import LayoutElementRole
from archium.domain.visual.layout import LayoutElement

TYPOGRAPHY_TOKEN_NAMES: tuple[str, ...] = (
    "display",
    "title",
    "subtitle",
    "heading",
    "body",
    "caption",
    "metric",
    "footnote",
    "source",
)


def typography_tokens_by_size(
    typography: TypographySystem,
) -> list[tuple[str, TextStyleToken]]:
    """Return named typography tokens sorted by actual font_size (then name)."""
    items = [(name, getattr(typography, name)) for name in TYPOGRAPHY_TOKEN_NAMES]
    return sorted(items, key=lambda item: (item[1].font_size, item[0]))


def role_min_font_pt(role: LayoutElementRole, thresholds: LayoutThresholds) -> float:
    """Minimum legal font size for a layout element role."""
    if role == LayoutElementRole.CAPTION:
        return thresholds.min_caption_font_pt
    if role in {LayoutElementRole.SOURCE, LayoutElementRole.FOOTER, LayoutElementRole.PAGE_NUMBER}:
        return thresholds.min_source_font_pt
    if role == LayoutElementRole.ANNOTATION:
        return thresholds.min_caption_font_pt
    if role in {
        LayoutElementRole.BODY_TEXT,
        LayoutElementRole.LEAD_STATEMENT,
        LayoutElementRole.TITLE,
        LayoutElementRole.SUBTITLE,
        LayoutElementRole.METRIC,
    }:
        return thresholds.min_body_font_pt
    return thresholds.min_source_font_pt


def base_text_style(element: LayoutElement, typography: TypographySystem) -> TextStyleToken:
    token_name = element.style_token or "body"
    return getattr(typography, token_name, typography.body)


def resolve_text_style(element: LayoutElement, typography: TypographySystem) -> TextStyleToken:
    """Token style with optional ``font_size_override`` applied (line-height scaled)."""
    base = base_text_style(element, typography)
    override = element.font_size_override
    if override is None:
        return base
    scale = override / max(base.font_size, 1e-6)
    return base.model_copy(
        update={
            "font_size": override,
            "line_height": max(0.01, base.line_height * scale),
        }
    )


def effective_font_size(element: LayoutElement, typography: TypographySystem) -> float:
    return resolve_text_style(element, typography).font_size


def next_larger_token(
    element: LayoutElement,
    *,
    typography: TypographySystem,
    minimum_pt: float,
) -> str | None:
    """Smallest named token strictly larger than the current effective size and >= minimum."""
    current_size = effective_font_size(element, typography)
    candidates = [
        (name, style)
        for name, style in typography_tokens_by_size(typography)
        if style.font_size + 1e-6 >= minimum_pt
        and style.font_size > current_size + 1e-6
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[1].font_size, item[0]))[0]


def smaller_compliant_tokens(
    element: LayoutElement,
    *,
    typography: TypographySystem,
    minimum_pt: float,
) -> list[str]:
    """Tokens smaller than current effective size but still >= role/threshold minimum.

    Ordered largest-first (least compact → more compact) so callers try gentle
    reductions before aggressive ones.
    """
    current_size = effective_font_size(element, typography)
    current_name = element.style_token or "body"
    smaller = [
        (name, style)
        for name, style in typography_tokens_by_size(typography)
        if name != current_name
        and style.font_size + 1e-6 >= minimum_pt
        and style.font_size + 1e-6 < current_size
    ]
    smaller.sort(key=lambda item: (-item[1].font_size, item[0]))
    return [name for name, _ in smaller]


def clamp_font_size_override(size_pt: float, *, minimum_pt: float, maximum_pt: float) -> float:
    """Clamp an override into the DesignSystem-legal band."""
    return min(max(size_pt, minimum_pt), maximum_pt)
