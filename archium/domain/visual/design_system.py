"""DesignSystem — reusable, versioned visual specification."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import ApprovalStatus
from archium.domain.visual.enums import (
    DesignSystemSource,
    GridType,
    ImageFit,
    PhotoTreatment,
)


class PageSystem(DomainModel):
    """Page size and safe margins."""

    width: float = Field(gt=0)
    height: float = Field(gt=0)
    unit: str = "in"
    margin_top: float = Field(ge=0)
    margin_right: float = Field(ge=0)
    margin_bottom: float = Field(ge=0)
    margin_left: float = Field(ge=0)
    safe_area_enabled: bool = True

    @property
    def content_width(self) -> float:
        return self.width - self.margin_left - self.margin_right

    @property
    def content_height(self) -> float:
        return self.height - self.margin_top - self.margin_bottom

    @model_validator(mode="after")
    def _validate_margins(self) -> PageSystem:
        if self.margin_left + self.margin_right >= self.width:
            raise ValueError("horizontal margins exceed page width")
        if self.margin_top + self.margin_bottom >= self.height:
            raise ValueError("vertical margins exceed page height")
        return self


class GridSystem(DomainModel):
    """Column / modular / drawing canvas grid."""

    grid_type: GridType = GridType.COLUMN
    columns: int = Field(default=12, ge=1, le=24)
    rows: int | None = Field(default=None, ge=1, le=24)
    gutter: float = Field(gt=0)
    row_gutter: float | None = Field(default=None, ge=0)
    baseline: float | None = Field(default=None, ge=0)
    modular_enabled: bool = False


class SpacingSystem(DomainModel):
    """Semantic spacing scale (page units, typically inches)."""

    xs: float = Field(gt=0)
    sm: float = Field(gt=0)
    md: float = Field(gt=0)
    lg: float = Field(gt=0)
    xl: float = Field(gt=0)
    xxl: float = Field(gt=0)

    @model_validator(mode="after")
    def _validate_scale(self) -> SpacingSystem:
        values = [self.xs, self.sm, self.md, self.lg, self.xl, self.xxl]
        if values != sorted(values):
            raise ValueError("spacing scale must be non-decreasing")
        return self


class TextStyleToken(DomainModel):
    """Named typography token."""

    font_family: str = Field(min_length=1)
    font_family_latin: str | None = None
    font_size: float = Field(gt=0)
    font_weight: int = Field(ge=100, le=900)
    line_height: float = Field(gt=0)
    letter_spacing: float = 0
    color_token: str = Field(min_length=1)
    alignment: str = "left"
    max_lines: int | None = Field(default=None, ge=1)


class TypographySystem(DomainModel):
    """Hierarchical text styles."""

    display: TextStyleToken
    title: TextStyleToken
    subtitle: TextStyleToken
    heading: TextStyleToken
    body: TextStyleToken
    caption: TextStyleToken
    metric: TextStyleToken
    footnote: TextStyleToken
    source: TextStyleToken


class ColorSystem(DomainModel):
    """Named color tokens (hex without # or with #)."""

    background: str
    surface: str
    primary_text: str
    secondary_text: str
    muted_text: str
    primary: str
    secondary: str
    accent: str
    warning: str
    success: str
    border: str
    overlay: str

    @field_validator(
        "background",
        "surface",
        "primary_text",
        "secondary_text",
        "muted_text",
        "primary",
        "secondary",
        "accent",
        "warning",
        "success",
        "border",
        "overlay",
    )
    @classmethod
    def _validate_hex(cls, value: str) -> str:
        cleaned = value.strip().lstrip("#")
        if len(cleaned) not in {3, 6, 8} or any(c not in "0123456789abcdefABCDEF" for c in cleaned):
            raise ValueError(f"invalid color token: {value}")
        return f"#{cleaned.upper()}" if not value.startswith("#") else f"#{cleaned.upper()}"

    def resolve(self, token: str) -> str:
        """Resolve a color token name to a hex value."""
        key = token.strip().lstrip("#")
        if hasattr(self, key):
            return str(getattr(self, key))
        # Allow direct hex passthrough for migration paths.
        if len(key) in {3, 6, 8} and all(c in "0123456789abcdefABCDEF" for c in key):
            return f"#{key.upper()}"
        raise KeyError(f"unknown color token: {token}")


class ImageStyleSystem(DomainModel):
    """Default image / drawing presentation rules."""

    default_fit: ImageFit = ImageFit.CONTAIN
    default_corner_radius: float = Field(default=0.0, ge=0)
    border_width: float = Field(default=0.0, ge=0)
    border_color_token: str = "border"
    photo_shadow: bool = False
    photo_treatment: PhotoTreatment = PhotoTreatment.SUBTLE_UNIFY
    drawing_background: str = "#FFFFFF"
    drawing_border_enabled: bool = True
    drawing_preserve_aspect_ratio: bool = True


class AnnotationStyleSystem(DomainModel):
    """Callout / label styling."""

    font_token: str = "caption"
    marker_size: float = Field(default=0.22, gt=0)
    line_weight: float = Field(default=0.75, gt=0)
    color_token: str = "accent"


class ChartStyleSystem(DomainModel):
    """Chart defaults."""

    palette_tokens: list[str] = Field(default_factory=lambda: ["primary", "accent", "secondary"])
    grid_color_token: str = "border"
    axis_color_token: str = "muted_text"


class TableStyleSystem(DomainModel):
    """Table defaults."""

    header_background_token: str = "surface"
    border_color_token: str = "border"
    font_token: str = "body"
    cell_padding: float = Field(default=0.05, ge=0)


class FooterStyleSystem(DomainModel):
    """Footer / page number / source strip."""

    enabled: bool = True
    font_token: str = "footnote"
    show_page_number: bool = True
    show_source: bool = True
    height: float = Field(default=0.35, gt=0)


class LayoutThresholds(DomainModel):
    """Validation thresholds owned by the design system (not scattered magic numbers)."""

    min_body_font_pt: float = Field(default=14.0, gt=0)
    min_caption_font_pt: float = Field(default=9.0, gt=0)
    min_source_font_pt: float = Field(default=8.0, gt=0)
    min_hero_area_ratio: float = Field(default=0.45, ge=0.0, le=1.0)
    min_whitespace_ratio: float = Field(default=0.08, ge=0.0, le=1.0)
    max_whitespace_ratio: float = Field(default=0.60, ge=0.0, le=1.0)
    max_title_lines: int = Field(default=2, ge=1)
    max_overlap_tolerance: float = Field(default=0.01, ge=0)


class DesignSystem(IdentifiedModel, VersionedModel, TimestampedModel):
    """Versioned visual specification independent of any single slide layout."""

    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    schema_version: int = Field(default=1, ge=1)
    page: PageSystem
    grid: GridSystem
    spacing: SpacingSystem
    typography: TypographySystem
    colors: ColorSystem
    image_style: ImageStyleSystem = Field(default_factory=ImageStyleSystem)
    annotation_style: AnnotationStyleSystem = Field(default_factory=AnnotationStyleSystem)
    chart_style: ChartStyleSystem = Field(default_factory=ChartStyleSystem)
    table_style: TableStyleSystem = Field(default_factory=TableStyleSystem)
    footer_style: FooterStyleSystem = Field(default_factory=FooterStyleSystem)
    thresholds: LayoutThresholds = Field(default_factory=LayoutThresholds)
    source_type: DesignSystemSource = DesignSystemSource.BUILTIN
    source_reference: str | None = None
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED

    def approve(self) -> None:
        self.approval_status = ApprovalStatus.APPROVED
        self.touch()

    def reject(self) -> None:
        self.approval_status = ApprovalStatus.REJECTED
        self.touch()
