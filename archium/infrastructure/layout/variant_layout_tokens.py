"""Semantic layout proportion tokens per family / variant.

Generators read these tokens instead of hard-coded inch fractions or magic
split ratios. Absolute coordinates are always derived at generation time from
page size, safe area, and content-aware body rects.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace

from archium.domain.visual.enums import LayoutFamily
from archium.infrastructure.layout.geometry import Rect


@dataclass(frozen=True)
class VariantLayoutTokens:
    """Proportional layout constraints for one family variant."""

    # Hero / primary visual dominance (share of body rect area after title band).
    hero_min_body_area_ratio: float = 0.58
    # Delivery-grade hero floor as share of safe-area (used by LayoutValidationService).
    hero_min_safe_area_ratio: float | None = None
    # Split layouts: max width share of the text / side panel within body.
    text_panel_max_width_ratio: float = 0.35
    # Drawing-focus split: primary visual width share within body (left panel).
    primary_visual_width_ratio: float = 0.72

    # Footer stack — heights as share of safe-area height; widths as share of safe width.
    caption_max_height_ratio: float = 0.12
    source_max_height_ratio: float = 0.05
    caption_width_ratio: float = 0.65
    source_width_ratio: float = 0.65

    # In-panel text bands
    lead_height_ratio: float = 0.5
    overlay_lead_y_ratio: float = 0.55
    overlay_lead_width_ratio: float = 0.45
    overlay_lead_height_ratio: float = 0.35

    title_band_min_height: float = 0.65


def _merge_tokens(base: VariantLayoutTokens, override: VariantLayoutTokens) -> VariantLayoutTokens:
    defaults = VariantLayoutTokens()
    updates = {
        field.name: getattr(override, field.name)
        for field in fields(VariantLayoutTokens)
        if getattr(override, field.name) != getattr(defaults, field.name)
    }
    return replace(base, **updates) if updates else base


_FAMILY_DEFAULTS: dict[LayoutFamily, VariantLayoutTokens] = {
    LayoutFamily.HERO: VariantLayoutTokens(
        text_panel_max_width_ratio=0.35,
        hero_min_body_area_ratio=0.58,
        hero_min_safe_area_ratio=0.50,
        caption_max_height_ratio=0.0,
        source_max_height_ratio=0.053,
        source_width_ratio=0.70,
    ),
    LayoutFamily.DRAWING_FOCUS: VariantLayoutTokens(
        primary_visual_width_ratio=0.72,
        hero_min_body_area_ratio=0.72,
        caption_max_height_ratio=0.059,
        source_max_height_ratio=0.047,
    ),
}

_VARIANT_OVERRIDES: dict[tuple[LayoutFamily, str], VariantLayoutTokens] = {
    (LayoutFamily.HERO, "split"): VariantLayoutTokens(
        text_panel_max_width_ratio=0.28,
        hero_min_body_area_ratio=0.58,
    ),
    (LayoutFamily.HERO, "full_bleed"): VariantLayoutTokens(
        hero_min_body_area_ratio=1.0,
        hero_min_safe_area_ratio=0.65,
        text_panel_max_width_ratio=0.0,
    ),
    (LayoutFamily.HERO, "overlay"): VariantLayoutTokens(
        hero_min_body_area_ratio=1.0,
        hero_min_safe_area_ratio=0.55,
        text_panel_max_width_ratio=0.0,
    ),
    (LayoutFamily.DRAWING_FOCUS, "full_canvas"): VariantLayoutTokens(
        primary_visual_width_ratio=1.0,
        hero_min_body_area_ratio=1.0,
    ),
}


def resolve_layout_tokens(family: LayoutFamily, variant: str) -> VariantLayoutTokens:
    """Return merged layout tokens for ``family`` + ``variant``."""
    base = _FAMILY_DEFAULTS.get(family, VariantLayoutTokens())
    override = _VARIANT_OVERRIDES.get((family, variant))
    if override is None:
        return base
    return _merge_tokens(base, override)


def effective_min_hero_area_ratio(
    family: LayoutFamily,
    variant: str,
    *,
    design_fallback: float,
) -> float:
    """Hero dominance floor for validation — variant token overrides design system."""
    tokens = resolve_layout_tokens(family, variant)
    if tokens.hero_min_safe_area_ratio is not None:
        return tokens.hero_min_safe_area_ratio
    return design_fallback


def compute_hero_split_text_ratio(
    body: Rect,
    tokens: VariantLayoutTokens,
    *,
    gap: float,
) -> float:
    """Left-panel width ratio that respects text cap and hero body-area floor."""
    if tokens.text_panel_max_width_ratio <= 0.0:
        return 0.0
    usable_w = max(1e-6, body.width - gap)
    ratio_for_hero = 1.0 - tokens.hero_min_body_area_ratio * body.width / usable_w
    capped = min(tokens.text_panel_max_width_ratio, ratio_for_hero)
    return max(0.15, min(0.45, capped))


def footer_band_heights(safe: Rect, tokens: VariantLayoutTokens) -> tuple[float, float]:
    """Return ``(caption_h, source_h)`` in page units from safe-area ratios."""
    caption_h = safe.height * tokens.caption_max_height_ratio if tokens.caption_max_height_ratio > 0 else 0.0
    source_h = safe.height * tokens.source_max_height_ratio
    return caption_h, source_h
