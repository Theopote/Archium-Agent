"""Pure functions: DeckThemeTokens → DesignSystem (deep copy, no persistence)."""

from __future__ import annotations

from archium.domain._base import new_uuid, utc_now
from archium.domain.visual.deck_theme_tokens import (
    _DENSITY_SPACING_SCALE,
    _ICON_STYLE_PRESETS,
    DeckThemeTokens,
)
from archium.domain.visual.design_system import (
    DesignSystem,
    SpacingSystem,
    TextStyleToken,
    TypographySystem,
)
from archium.domain.visual.enums import DesignSystemSource, ImageFit


def apply_tokens_to_design_system(
    base: DesignSystem,
    tokens: DeckThemeTokens,
) -> DesignSystem:
    """Return a new DesignSystem id/version with token overrides applied.

    Drawing fit stays ``contain`` — photo treatment never flips drawing cover.
    """
    proposed = base.model_copy(deep=True)
    proposed = proposed.model_copy(
        update={
            "id": new_uuid(),
            "version": base.version + 1,
            "source_type": DesignSystemSource.USER,
            "source_reference": f"theme_tokens:{base.id}",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "name": _theme_name(base.name),
        }
    )

    if tokens.primary is not None:
        proposed.colors.primary = tokens.primary
    if tokens.accent is not None:
        proposed.colors.accent = tokens.accent
    if tokens.background is not None:
        proposed.colors.background = tokens.background

    if tokens.title_font is not None:
        proposed.typography = _replace_title_fonts(proposed.typography, tokens.title_font)
    if tokens.body_font is not None:
        proposed.typography = _replace_body_fonts(proposed.typography, tokens.body_font)
    if tokens.title_scale is not None and abs(tokens.title_scale - 1.0) > 1e-9:
        proposed.typography = _scale_title_sizes(proposed.typography, tokens.title_scale)

    if tokens.page_density is not None:
        scale = _DENSITY_SPACING_SCALE[tokens.page_density]
        if abs(scale - 1.0) > 1e-9:
            proposed.spacing = _scale_spacing(proposed.spacing, scale)

    image_style = proposed.image_style.model_copy(deep=True)
    if tokens.corner_radius is not None:
        image_style.default_corner_radius = tokens.corner_radius
    if tokens.line_weight is not None:
        image_style.border_width = tokens.line_weight
    if tokens.photo_treatment is not None:
        image_style.photo_treatment = tokens.photo_treatment
    # Never let theme tokens force drawing cover.
    if image_style.default_fit == ImageFit.COVER:
        image_style.default_fit = ImageFit.CONTAIN
    proposed.image_style = image_style

    annotation = proposed.annotation_style.model_copy(deep=True)
    if tokens.line_weight is not None:
        annotation.line_weight = tokens.line_weight
    if tokens.icon_style is not None:
        marker_size, icon_line = _ICON_STYLE_PRESETS[tokens.icon_style]
        annotation.marker_size = marker_size
        if tokens.line_weight is None:
            annotation.line_weight = icon_line
    proposed.annotation_style = annotation

    return proposed


def deck_theme_tokens_from_design_system(design: DesignSystem) -> DeckThemeTokens:
    """Seed Studio controls from the active DesignSystem."""
    return DeckThemeTokens(
        primary=design.colors.primary,
        accent=design.colors.accent,
        background=design.colors.background,
        title_font=design.typography.title.font_family,
        body_font=design.typography.body.font_family,
        title_scale=1.0,
        page_density="balanced",
        corner_radius=design.image_style.default_corner_radius,
        line_weight=design.annotation_style.line_weight,
        photo_treatment=design.image_style.photo_treatment,
        icon_style="filled",
    )


def _theme_name(base_name: str) -> str:
    suffix = " (theme proposal)"
    if base_name.endswith(suffix):
        return base_name
    return f"{base_name}{suffix}"


def _replace_title_fonts(typography: TypographySystem, font: str) -> TypographySystem:
    return typography.model_copy(
        update={
            "display": _with_font(typography.display, font),
            "title": _with_font(typography.title, font),
            "heading": _with_font(typography.heading, font),
            "subtitle": _with_font(typography.subtitle, font),
        }
    )


def _replace_body_fonts(typography: TypographySystem, font: str) -> TypographySystem:
    return typography.model_copy(
        update={
            "body": _with_font(typography.body, font),
            "caption": _with_font(typography.caption, font),
            "metric": _with_font(typography.metric, font),
            "footnote": _with_font(typography.footnote, font),
            "source": _with_font(typography.source, font),
        }
    )


def _scale_title_sizes(typography: TypographySystem, scale: float) -> TypographySystem:
    return typography.model_copy(
        update={
            "display": _scale_font(typography.display, scale),
            "title": _scale_font(typography.title, scale),
            "heading": _scale_font(typography.heading, scale),
            "subtitle": _scale_font(typography.subtitle, scale),
        }
    )


def _scale_spacing(spacing: SpacingSystem, scale: float) -> SpacingSystem:
    return SpacingSystem(
        xs=spacing.xs * scale,
        sm=spacing.sm * scale,
        md=spacing.md * scale,
        lg=spacing.lg * scale,
        xl=spacing.xl * scale,
        xxl=spacing.xxl * scale,
    )


def _with_font(token: TextStyleToken, font: str) -> TextStyleToken:
    return token.model_copy(update={"font_family": font})


def _scale_font(token: TextStyleToken, scale: float) -> TextStyleToken:
    return token.model_copy(
        update={
            "font_size": round(token.font_size * scale, 2),
            "line_height": round(token.line_height * scale, 2),
        }
    )
