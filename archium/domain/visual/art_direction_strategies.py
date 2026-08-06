"""
Structured strategy models for ArtDirection.

Replaces string-based strategies with executable, structured objects.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from archium.domain._base import DomainModel


class PaletteStrategy(DomainModel):
    """
    Structured color palette strategy.

    Defines measurable color characteristics that can be executed
    by the design system.
    """

    saturation: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Color saturation level (0=grayscale, 1=fully saturated)",
    )

    brightness: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Overall brightness/lightness (0=dark, 1=light)",
    )

    contrast: Literal["low", "medium", "high", "extreme"] = Field(
        default="medium",
        description="Contrast level between colors",
    )

    temperature: Literal["cool", "neutral", "warm"] = Field(
        default="neutral",
        description="Color temperature bias",
    )

    accent_intensity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How bold/prominent accent colors should be (0=subtle, 1=bold)",
    )

    palette_size: Literal["minimal", "balanced", "rich"] = Field(
        default="balanced",
        description="Number of distinct colors to use",
    )

    monochrome: bool = Field(
        default=False,
        description="Whether to use a monochromatic palette",
    )


class TypographyStrategy(DomainModel):
    """
    Structured typography strategy.

    Defines measurable typographic characteristics.
    """

    scale_ratio: float = Field(
        default=1.25,
        ge=1.1,
        le=2.0,
        description="Type scale multiplier between hierarchical levels",
    )

    weight_contrast: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Font weight variation between elements",
    )

    tracking: Literal["tight", "normal", "loose", "very_loose"] = Field(
        default="normal",
        description="Letter spacing characteristics",
    )

    leading: Literal["tight", "normal", "loose"] = Field(
        default="normal",
        description="Line height / leading",
    )

    alignment_bias: Literal["left", "center", "mixed"] = Field(
        default="left",
        description="Default text alignment preference",
    )

    case_style: Literal["sentence", "title", "uppercase", "mixed"] = Field(
        default="sentence",
        description="Capitalization style for headings",
    )


class GridStrategy(DomainModel):
    """
    Structured grid and spacing strategy.

    Defines layout grid characteristics.
    """

    column_count: int = Field(
        default=12,
        ge=1,
        le=24,
        description="Number of grid columns",
    )

    gutter_width: Literal["tight", "normal", "loose", "generous"] = Field(
        default="normal",
        description="Space between grid columns",
    )

    margin_strategy: Literal["minimal", "balanced", "generous", "asymmetric"] = Field(
        default="balanced",
        description="Page margin approach",
    )

    grid_type: Literal["modular", "hierarchical", "compound", "manuscript"] = Field(
        default="modular",
        description="Grid system type",
    )

    baseline_grid: bool = Field(
        default=False,
        description="Whether to use a baseline grid",
    )

    rhythm_unit: float = Field(
        default=8.0,
        gt=0,
        description="Base spacing unit in points",
    )


class ImageStrategy(DomainModel):
    """
    Structured image treatment strategy.

    Defines how images should be treated visually.
    """

    dominant_size: Literal["small", "medium", "large", "hero"] = Field(
        default="large",
        description="Typical image size preference",
    )

    crop_style: Literal["contained", "covered", "artistic"] = Field(
        default="covered",
        description="How images should be cropped",
    )

    edge_treatment: Literal["sharp", "rounded", "organic"] = Field(
        default="sharp",
        description="Image corner treatment",
    )

    overlay_intensity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Color overlay intensity (0=none, 1=full)",
    )

    filter_style: Literal["none", "subtle", "dramatic", "black_white"] = Field(
        default="none",
        description="Image filter/adjustment style",
    )

    bleed_preference: bool = Field(
        default=True,
        description="Whether images should bleed to edges",
    )


class DiagramStrategy(DomainModel):
    """
    Structured diagram and technical drawing strategy.
    """

    line_weight: Literal["hairline", "light", "medium", "bold"] = Field(
        default="medium",
        description="Default line weight for diagrams",
    )

    annotation_density: Literal["minimal", "balanced", "detailed"] = Field(
        default="balanced",
        description="Amount of annotations/labels",
    )

    color_coding: bool = Field(
        default=True,
        description="Whether to use color to distinguish elements",
    )

    dimension_style: Literal["minimal", "standard", "detailed"] = Field(
        default="standard",
        description="Dimensioning detail level",
    )

    drawing_style: Literal["technical", "sketch", "hybrid"] = Field(
        default="technical",
        description="Overall drawing aesthetic",
    )


# Helper function to convert legacy strings to structured strategies
def palette_strategy_from_string(description: str) -> PaletteStrategy:
    """
    Infer PaletteStrategy from legacy string description.

    This is a best-effort conversion for migration purposes.
    """
    desc_lower = description.lower()

    # Detect saturation
    saturation = 0.6  # default
    if "desaturated" in desc_lower or "muted" in desc_lower:
        saturation = 0.3
    elif "saturated" in desc_lower or "bold" in desc_lower or "vibrant" in desc_lower:
        saturation = 0.8
    elif "grayscale" in desc_lower or "monochrome" in desc_lower:
        saturation = 0.0

    # Detect brightness
    brightness = 0.7  # default
    if "dark" in desc_lower or "moody" in desc_lower:
        brightness = 0.3
    elif "light" in desc_lower or "bright" in desc_lower or "airy" in desc_lower:
        brightness = 0.9

    # Detect contrast
    contrast: Literal["low", "medium", "high", "extreme"] = "medium"
    if "high contrast" in desc_lower or "stark" in desc_lower:
        contrast = "high"
    elif "low contrast" in desc_lower or "subtle" in desc_lower:
        contrast = "low"
    elif "extreme" in desc_lower:
        contrast = "extreme"

    # Detect temperature
    temperature: Literal["cool", "neutral", "warm"] = "neutral"
    if "warm" in desc_lower or "orange" in desc_lower or "red" in desc_lower:
        temperature = "warm"
    elif "cool" in desc_lower or "blue" in desc_lower or "cyan" in desc_lower:
        temperature = "cool"

    # Detect monochrome
    monochrome = "monochrome" in desc_lower or "grayscale" in desc_lower

    # Detect palette size
    palette_size: Literal["minimal", "balanced", "rich"] = "balanced"
    if "minimal" in desc_lower or "restrained" in desc_lower:
        palette_size = "minimal"
    elif "rich" in desc_lower or "diverse" in desc_lower:
        palette_size = "rich"

    return PaletteStrategy(
        saturation=saturation,
        brightness=brightness,
        contrast=contrast,
        temperature=temperature,
        accent_intensity=0.7 if "bold" in desc_lower else 0.5,
        palette_size=palette_size,
        monochrome=monochrome,
    )


def typography_strategy_from_string(description: str) -> TypographyStrategy:
    """Infer TypographyStrategy from legacy string description."""
    desc_lower = description.lower()

    # Detect scale ratio
    scale_ratio = 1.25  # default
    if "dramatic" in desc_lower or "large scale" in desc_lower:
        scale_ratio = 1.5
    elif "subtle" in desc_lower or "minimal" in desc_lower:
        scale_ratio = 1.15

    # Detect weight contrast
    weight_contrast: Literal["low", "medium", "high"] = "medium"
    if "bold" in desc_lower or "strong" in desc_lower:
        weight_contrast = "high"
    elif "subtle" in desc_lower or "uniform" in desc_lower:
        weight_contrast = "low"

    # Detect tracking
    tracking: Literal["tight", "normal", "loose", "very_loose"] = "normal"
    if "tight" in desc_lower or "condensed" in desc_lower:
        tracking = "tight"
    elif "loose" in desc_lower or "spacious" in desc_lower:
        tracking = "loose"
    elif "very loose" in desc_lower or "generous" in desc_lower:
        tracking = "very_loose"

    # Detect case style
    case_style: Literal["sentence", "title", "uppercase", "mixed"] = "sentence"
    if "uppercase" in desc_lower or "all caps" in desc_lower:
        case_style = "uppercase"
    elif "title case" in desc_lower:
        case_style = "title"

    return TypographyStrategy(
        scale_ratio=scale_ratio,
        weight_contrast=weight_contrast,
        tracking=tracking,
        leading="normal",
        alignment_bias="left",
        case_style=case_style,
    )


def grid_strategy_from_string(description: str) -> GridStrategy:
    """Infer GridStrategy from legacy string description."""
    desc_lower = description.lower()

    # Detect margin strategy
    margin_strategy: Literal["minimal", "balanced", "generous", "asymmetric"] = "balanced"
    if "minimal" in desc_lower or "tight" in desc_lower:
        margin_strategy = "minimal"
    elif "generous" in desc_lower or "spacious" in desc_lower:
        margin_strategy = "generous"
    elif "asymmetric" in desc_lower:
        margin_strategy = "asymmetric"

    # Detect grid type
    grid_type: Literal["modular", "hierarchical", "compound", "manuscript"] = "modular"
    if "hierarchical" in desc_lower:
        grid_type = "hierarchical"
    elif "manuscript" in desc_lower or "single column" in desc_lower:
        grid_type = "manuscript"
    elif "compound" in desc_lower:
        grid_type = "compound"

    return GridStrategy(
        column_count=12,
        gutter_width="normal",
        margin_strategy=margin_strategy,
        grid_type=grid_type,
        baseline_grid=False,
        rhythm_unit=8.0,
    )
