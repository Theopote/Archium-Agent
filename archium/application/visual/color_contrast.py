"""WCAG-ish text vs background contrast helpers (Visual readability).

Used by color composition, RenderScene compile, and VQ-007 refinement.
"""

from __future__ import annotations

import re

# WCAG 2.x approximate thresholds.
MIN_CONTRAST_BODY = 4.5
MIN_CONTRAST_LARGE = 3.0  # large text (~18pt+ or ≥14pt bold)
MIN_CONTRAST_CAPTION = 3.0
MIN_CONTRAST_GHOST = 1.15  # decorative; still avoid near-invisible on same luminance

_NEAR_BLACK = "#121212"
_NEAR_WHITE = "#F7F7F5"


def parse_hex(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    cleaned = str(value).strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{3}|[0-9a-fA-F]{6}", cleaned):
        return None
    if len(cleaned) == 3:
        cleaned = "".join(ch * 2 for ch in cleaned)
    return int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16)


def relative_luminance(hex_color: str | None) -> float | None:
    rgb = parse_hex(hex_color)
    if rgb is None:
        return None

    def _channel(value: int) -> float:
        c = value / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(hex_a: str | None, hex_b: str | None) -> float:
    """WCAG contrast ratio; returns 21 when either color is unparseable."""
    a = relative_luminance(hex_a)
    b = relative_luminance(hex_b)
    if a is None or b is None:
        return 21.0
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def is_large_text(*, font_size: float, font_weight: int = 400) -> bool:
    if font_size >= 18.0:
        return True
    return font_size >= 14.0 and font_weight >= 700


def min_ratio_for_role(
    semantic_role: str,
    *,
    font_size: float = 14.0,
    font_weight: int = 400,
) -> float:
    role = (semantic_role or "").lower()
    if "ghost" in role:
        return MIN_CONTRAST_GHOST
    if role in {"caption", "annotation", "footnote", "citation", "source", "footer"}:
        return MIN_CONTRAST_CAPTION
    if role in {"title", "subtitle", "section_title", "cover_title", "metric"} or is_large_text(
        font_size=font_size, font_weight=font_weight
    ):
        return MIN_CONTRAST_LARGE
    return MIN_CONTRAST_BODY


def preferred_ink_on(background_hex: str | None) -> str:
    """Pick near-black or near-white ink for maximum contrast on ``background_hex``."""
    bg_l = relative_luminance(background_hex)
    if bg_l is None:
        return _NEAR_BLACK
    # Mid-gray boards still need dark ink for body copy.
    return _NEAR_WHITE if bg_l < 0.45 else _NEAR_BLACK


def ensure_contrast(
    foreground_hex: str | None,
    background_hex: str | None,
    *,
    min_ratio: float = MIN_CONTRAST_BODY,
) -> str:
    """Return a foreground hex that meets ``min_ratio`` against the background.

    Prefer keeping the original color when it already passes; otherwise snap to
    the higher-contrast pole (near-black / near-white).
    """
    bg = background_hex or _NEAR_WHITE
    fg = foreground_hex or preferred_ink_on(bg)
    if contrast_ratio(fg, bg) >= min_ratio:
        return fg if fg.startswith("#") else f"#{fg.lstrip('#')}"

    black_ratio = contrast_ratio(_NEAR_BLACK, bg)
    white_ratio = contrast_ratio(_NEAR_WHITE, bg)
    if black_ratio >= white_ratio and black_ratio >= min_ratio:
        return _NEAR_BLACK
    if white_ratio >= min_ratio:
        return _NEAR_WHITE
    # Last resort: still pick the stronger pole even if under threshold.
    return _NEAR_BLACK if black_ratio >= white_ratio else _NEAR_WHITE


def ensure_readable_pair(
    background_hex: str | None,
    text_hex: str | None,
    *,
    min_ratio: float = MIN_CONTRAST_BODY,
) -> tuple[str, str]:
    """Guarantee a readable (background, text) pair; background unchanged."""
    bg = background_hex or _NEAR_WHITE
    if not bg.startswith("#"):
        bg = f"#{bg.lstrip('#')}"
    text = ensure_contrast(text_hex, bg, min_ratio=min_ratio)
    return bg, text


__all__ = [
    "MIN_CONTRAST_BODY",
    "MIN_CONTRAST_CAPTION",
    "MIN_CONTRAST_GHOST",
    "MIN_CONTRAST_LARGE",
    "contrast_ratio",
    "ensure_contrast",
    "ensure_readable_pair",
    "is_large_text",
    "min_ratio_for_role",
    "parse_hex",
    "preferred_ink_on",
    "relative_luminance",
]
