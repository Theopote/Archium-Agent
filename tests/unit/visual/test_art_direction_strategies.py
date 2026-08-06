"""
Tests for structured ArtDirection strategies
"""

import pytest

from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.art_direction_strategies import (
    GridStrategy,
    PaletteStrategy,
    TypographyStrategy,
    grid_strategy_from_string,
    palette_strategy_from_string,
    typography_strategy_from_string,
)


class TestPaletteStrategy:
    """Test PaletteStrategy model."""

    def test_palette_strategy_defaults(self):
        """Test default palette strategy."""
        strategy = PaletteStrategy()

        assert strategy.saturation == 0.6
        assert strategy.brightness == 0.7
        assert strategy.contrast == "medium"
        assert strategy.temperature == "neutral"
        assert strategy.accent_intensity == 0.5
        assert strategy.palette_size == "balanced"
        assert strategy.monochrome is False

    def test_palette_strategy_custom(self):
        """Test custom palette strategy."""
        strategy = PaletteStrategy(
            saturation=0.8,
            brightness=0.9,
            contrast="high",
            temperature="warm",
            accent_intensity=0.9,
            palette_size="rich",
            monochrome=False,
        )

        assert strategy.saturation == 0.8
        assert strategy.brightness == 0.9
        assert strategy.contrast == "high"
        assert strategy.temperature == "warm"
        assert strategy.accent_intensity == 0.9
        assert strategy.palette_size == "rich"

    def test_palette_strategy_from_string_saturated(self):
        """Test converting saturated string to strategy."""
        strategy = palette_strategy_from_string("use bold, saturated colors with high contrast")

        assert strategy.saturation >= 0.7
        assert strategy.contrast == "high"

    def test_palette_strategy_from_string_muted(self):
        """Test converting muted string to strategy."""
        strategy = palette_strategy_from_string("muted, desaturated palette with subtle tones")

        assert strategy.saturation <= 0.4
        assert strategy.contrast == "low"

    def test_palette_strategy_from_string_monochrome(self):
        """Test converting monochrome string to strategy."""
        strategy = palette_strategy_from_string("grayscale monochrome palette")

        assert strategy.saturation == 0.0
        assert strategy.monochrome is True


class TestTypographyStrategy:
    """Test TypographyStrategy model."""

    def test_typography_strategy_defaults(self):
        """Test default typography strategy."""
        strategy = TypographyStrategy()

        assert strategy.scale_ratio == 1.25
        assert strategy.weight_contrast == "medium"
        assert strategy.tracking == "normal"
        assert strategy.leading == "normal"
        assert strategy.alignment_bias == "left"
        assert strategy.case_style == "sentence"

    def test_typography_strategy_custom(self):
        """Test custom typography strategy."""
        strategy = TypographyStrategy(
            scale_ratio=1.5,
            weight_contrast="high",
            tracking="loose",
            leading="loose",
            alignment_bias="center",
            case_style="uppercase",
        )

        assert strategy.scale_ratio == 1.5
        assert strategy.weight_contrast == "high"
        assert strategy.tracking == "loose"
        assert strategy.case_style == "uppercase"

    def test_typography_strategy_from_string_dramatic(self):
        """Test converting dramatic string to strategy."""
        strategy = typography_strategy_from_string("dramatic scale with bold weights and loose tracking")

        assert strategy.scale_ratio >= 1.4
        assert strategy.weight_contrast == "high"
        assert strategy.tracking == "loose"

    def test_typography_strategy_from_string_uppercase(self):
        """Test converting uppercase string to strategy."""
        strategy = typography_strategy_from_string("all caps uppercase headings")

        assert strategy.case_style == "uppercase"


class TestGridStrategy:
    """Test GridStrategy model."""

    def test_grid_strategy_defaults(self):
        """Test default grid strategy."""
        strategy = GridStrategy()

        assert strategy.column_count == 12
        assert strategy.gutter_width == "normal"
        assert strategy.margin_strategy == "balanced"
        assert strategy.grid_type == "modular"
        assert strategy.baseline_grid is False
        assert strategy.rhythm_unit == 8.0

    def test_grid_strategy_custom(self):
        """Test custom grid strategy."""
        strategy = GridStrategy(
            column_count=16,
            gutter_width="generous",
            margin_strategy="asymmetric",
            grid_type="hierarchical",
            baseline_grid=True,
            rhythm_unit=10.0,
        )

        assert strategy.column_count == 16
        assert strategy.gutter_width == "generous"
        assert strategy.margin_strategy == "asymmetric"
        assert strategy.grid_type == "hierarchical"
        assert strategy.baseline_grid is True

    def test_grid_strategy_from_string_asymmetric(self):
        """Test converting asymmetric string to strategy."""
        strategy = grid_strategy_from_string("asymmetric margins with generous spacing")

        assert strategy.margin_strategy == "asymmetric"

    def test_grid_strategy_from_string_hierarchical(self):
        """Test converting hierarchical string to strategy."""
        strategy = grid_strategy_from_string("hierarchical grid structure")

        assert strategy.grid_type == "hierarchical"


class TestArtDirectionStructuredStrategies:
    """Test ArtDirection with structured strategies."""

    def test_art_direction_with_structured_palette(self):
        """Test ArtDirection with structured palette strategy."""
        from uuid import uuid4

        art_direction = ArtDirection(
            id=uuid4(),
            project_id=uuid4(),
            concept_name="Bold Modern",
            rationale="Contemporary architectural expression",
            palette_strategy=PaletteStrategy(
                saturation=0.8,
                brightness=0.9,
                contrast="high",
            ),
            typography_strategy="minimal sans-serif with strong hierarchy",
            grid_strategy="12-column modular grid",
            image_strategy="hero images with sharp crops",
            drawing_strategy="precise technical drawings",
            diagram_strategy="color-coded analytical diagrams",
            annotation_strategy="minimal annotations",
            cover_strategy="bold hero with minimal text",
            section_strategy="clear section breaks",
            content_strategy="image-led storytelling",
            closing_strategy="strong closing statement",
            pacing_strategy="varied rhythm",
        )

        assert art_direction.has_structured_palette() is True
        assert art_direction.has_structured_typography() is False
        assert art_direction.has_structured_grid() is False

        palette = art_direction.get_palette_strategy()
        assert isinstance(palette, PaletteStrategy)
        assert palette.saturation == 0.8

    def test_art_direction_with_dict_coercion(self):
        """Test that dict is automatically coerced to PaletteStrategy."""
        from uuid import uuid4

        art_direction = ArtDirection(
            id=uuid4(),
            project_id=uuid4(),
            concept_name="Test",
            rationale="Test rationale",
            palette_strategy={
                "saturation": 0.9,
                "brightness": 0.8,
                "contrast": "extreme",
                "temperature": "warm",
            },
            typography_strategy="test typography",
            grid_strategy="test grid",
            image_strategy="test",
            drawing_strategy="test",
            diagram_strategy="test",
            annotation_strategy="test",
            cover_strategy="test",
            section_strategy="test",
            content_strategy="test",
            closing_strategy="test",
            pacing_strategy="test",
        )

        assert art_direction.has_structured_palette() is True
        palette = art_direction.palette_strategy
        assert isinstance(palette, PaletteStrategy)
        assert palette.saturation == 0.9
        assert palette.contrast == "extreme"

    def test_art_direction_with_legacy_string(self):
        """Test ArtDirection with legacy string strategy."""
        from uuid import uuid4

        art_direction = ArtDirection(
            id=uuid4(),
            project_id=uuid4(),
            concept_name="Legacy",
            rationale="Legacy rationale",
            palette_strategy="bold saturated colors",
            typography_strategy="strong typography",
            grid_strategy="modular grid",
            image_strategy="test",
            drawing_strategy="test",
            diagram_strategy="test",
            annotation_strategy="test",
            cover_strategy="test",
            section_strategy="test",
            content_strategy="test",
            closing_strategy="test",
            pacing_strategy="test",
        )

        assert art_direction.has_structured_palette() is False
        assert isinstance(art_direction.palette_strategy, str)

        # get_palette_strategy() should convert on the fly
        palette = art_direction.get_palette_strategy()
        assert isinstance(palette, PaletteStrategy)
        assert palette.saturation >= 0.7  # "saturated" detected

    def test_art_direction_all_structured(self):
        """Test ArtDirection with all three strategies structured."""
        from uuid import uuid4

        art_direction = ArtDirection(
            id=uuid4(),
            project_id=uuid4(),
            concept_name="Fully Structured",
            rationale="Modern approach",
            palette_strategy=PaletteStrategy(saturation=0.7),
            typography_strategy=TypographyStrategy(scale_ratio=1.4),
            grid_strategy=GridStrategy(column_count=16),
            image_strategy="test",
            drawing_strategy="test",
            diagram_strategy="test",
            annotation_strategy="test",
            cover_strategy="test",
            section_strategy="test",
            content_strategy="test",
            closing_strategy="test",
            pacing_strategy="test",
        )

        assert art_direction.has_structured_palette() is True
        assert art_direction.has_structured_typography() is True
        assert art_direction.has_structured_grid() is True

        palette = art_direction.get_palette_strategy()
        typography = art_direction.get_typography_strategy()
        grid = art_direction.get_grid_strategy()

        assert isinstance(palette, PaletteStrategy)
        assert isinstance(typography, TypographyStrategy)
        assert isinstance(grid, GridStrategy)

        assert palette.saturation == 0.7
        assert typography.scale_ratio == 1.4
        assert grid.column_count == 16


class TestStrategyConversion:
    """Test conversion from legacy strings to structured strategies."""

    def test_complex_palette_string(self):
        """Test converting complex palette description."""
        strategy = palette_strategy_from_string(
            "use a warm, saturated palette with high contrast and bold accents"
        )

        assert strategy.temperature == "warm"
        assert strategy.saturation >= 0.7
        assert strategy.contrast == "high"
        assert strategy.accent_intensity >= 0.6

    def test_complex_typography_string(self):
        """Test converting complex typography description."""
        strategy = typography_strategy_from_string(
            "dramatic type scale with bold weights, tight tracking, and uppercase headings"
        )

        assert strategy.scale_ratio >= 1.4
        assert strategy.weight_contrast == "high"
        assert strategy.tracking == "tight"
        assert strategy.case_style == "uppercase"

    def test_minimal_palette_string(self):
        """Test converting minimal palette description."""
        strategy = palette_strategy_from_string(
            "minimal monochrome grayscale with subtle tones"
        )

        assert strategy.monochrome is True
        assert strategy.saturation == 0.0
        assert strategy.palette_size == "minimal"
        assert strategy.contrast == "low"
