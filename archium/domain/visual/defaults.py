"""Built-in DesignSystem presets migrated from pptxgen theme.mjs tokens."""

from __future__ import annotations

from archium.domain.enums import ApprovalStatus
from archium.domain.visual.design_system import (
    ColorSystem,
    DesignSystem,
    FooterStyleSystem,
    GridSystem,
    ImageStyleSystem,
    LayoutThresholds,
    PageSystem,
    SpacingSystem,
    TextStyleToken,
    TypographySystem,
)
from archium.domain.visual.enums import DesignSystemSource, GridType, ImageFit, PhotoTreatment

# Semantic spacing scale derived from 4/8/12/16/24/32 px at 96 dpi → inches.
_SPACING = SpacingSystem(
    xs=4 / 96,
    sm=8 / 96,
    md=12 / 96,
    lg=16 / 96,
    xl=24 / 96,
    xxl=32 / 96,
)

_PAGE_16X9 = PageSystem(
    width=10.0,
    height=5.625,
    unit="in",
    margin_top=0.45,
    margin_right=0.7,
    margin_bottom=0.45,
    margin_left=0.7,
    safe_area_enabled=True,
)


def _text(
    *,
    size: float,
    weight: int,
    color: str,
    max_lines: int | None = None,
    alignment: str = "left",
    line_height: float | None = None,
) -> TextStyleToken:
    return TextStyleToken(
        font_family="Microsoft YaHei",
        font_family_latin="Arial",
        font_size=size,
        font_weight=weight,
        line_height=line_height if line_height is not None else round(size * 1.35, 2),
        color_token=color,
        alignment=alignment,
        max_lines=max_lines,
    )


def _architecture_board_colors() -> ColorSystem:
    return ColorSystem(
        background="#F7F6F3",
        surface="#FFFFFF",
        primary_text="#1A1A1A",
        secondary_text="#4A4A4A",
        muted_text="#777777",
        primary="#2C3E50",
        secondary="#5B6770",
        accent="#8B4513",
        warning="#C47B2B",
        success="#3D6B4F",
        border="#D9D5CF",
        overlay="#00000033",
    )


def _typography() -> TypographySystem:
    return TypographySystem(
        display=_text(size=38, weight=700, color="primary_text", max_lines=2),
        title=_text(size=34, weight=700, color="primary_text", max_lines=2),
        subtitle=_text(size=18, weight=400, color="secondary_text", max_lines=2),
        heading=_text(size=24, weight=700, color="primary_text", max_lines=2),
        body=_text(size=16, weight=400, color="primary_text"),
        caption=_text(size=12, weight=400, color="muted_text", max_lines=3),
        metric=_text(size=22, weight=700, color="primary", alignment="center"),
        footnote=_text(size=9, weight=400, color="muted_text", max_lines=1),
        source=_text(size=8, weight=400, color="muted_text", max_lines=1),
    )


def default_presentation_design_system(*, name: str = "architecture-board") -> DesignSystem:
    """Return the built-in 16:9 presentation DesignSystem (architecture-board)."""
    return DesignSystem(
        name=name,
        description="Default 16:9 architectural presentation system migrated from theme.mjs.",
        schema_version=1,
        page=_PAGE_16X9,
        grid=GridSystem(
            grid_type=GridType.COLUMN,
            columns=12,
            rows=None,
            gutter=0.4,
            row_gutter=0.2,
            modular_enabled=False,
        ),
        spacing=_SPACING,
        typography=_typography(),
        colors=_architecture_board_colors(),
        image_style=ImageStyleSystem(
            default_fit=ImageFit.CONTAIN,
            default_corner_radius=0.0,
            border_width=0.0,
            border_color_token="border",
            photo_shadow=False,
            photo_treatment=PhotoTreatment.SUBTLE_UNIFY,
            drawing_background="#FFFFFF",
            drawing_border_enabled=True,
            drawing_preserve_aspect_ratio=True,
        ),
        footer_style=FooterStyleSystem(
            enabled=True,
            font_token="footnote",
            show_page_number=True,
            show_source=True,
            height=0.35,
        ),
        thresholds=LayoutThresholds(),
        source_type=DesignSystemSource.BUILTIN,
        source_reference="pptxgen/core/theme.mjs#architecture-board",
        approval_status=ApprovalStatus.APPROVED,
    )


def drawing_canvas_design_system() -> DesignSystem:
    """Variant emphasizing drawing-canvas grid for technical plan pages."""
    base = default_presentation_design_system(name="drawing-canvas")
    return base.model_copy(
        update={
            "description": "16:9 system with drawing-canvas grid for technical drawings.",
            "grid": GridSystem(
                grid_type=GridType.DRAWING_CANVAS,
                columns=12,
                rows=8,
                gutter=0.25,
                row_gutter=0.15,
                modular_enabled=True,
            ),
            "source_reference": "builtin:drawing-canvas",
        }
    )
