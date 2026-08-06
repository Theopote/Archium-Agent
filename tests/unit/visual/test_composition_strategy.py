"""Tests for CompositionStrategy domain model."""

import pytest

from archium.domain.visual.composition_strategy import (
    ARCHETYPE_PRESETS,
    CompositionAxis,
    CompositionStrategy,
    ImageRole,
    LayeringStrategy,
    MarginsStrategy,
    ReadingPathType,
    TypographyRole,
    VisualBalance,
    VisualTension,
    WhiteSpaceStrategy,
    get_preset_strategy,
    suggest_strategy_for_content,
)


class TestCompositionStrategyModel:
    """Test CompositionStrategy domain model validation and methods."""

    def test_minimal_valid_strategy(self) -> None:
        """Test creation with minimal required fields."""
        strategy = CompositionStrategy(
            archetype="custom",
            dominant_axis=CompositionAxis.HORIZONTAL,
            reading_path=ReadingPathType.LINEAR_LTR,
            tension=VisualTension.SYMMETRIC,
            balance=VisualBalance.CENTERED,
            image_role=ImageRole.SUPPORTING,
            typography_role=TypographyRole.NARRATIVE,
            white_space=WhiteSpaceStrategy.BALANCED,
        )
        assert strategy.archetype == "custom"
        assert strategy.dominant_axis == CompositionAxis.HORIZONTAL
        assert strategy.margins == MarginsStrategy.STANDARD  # default
        assert strategy.layering == LayeringStrategy.FLAT  # default

    def test_full_strategy_with_all_fields(self) -> None:
        """Test creation with all optional fields populated."""
        strategy = CompositionStrategy(
            archetype="architectural_editorial",
            dominant_axis=CompositionAxis.DIAGONAL,
            focal_point=(0.4, 0.6),
            visual_hierarchy=["hero_image", "title", "body_text"],
            reading_path=ReadingPathType.Z_PATTERN,
            tension=VisualTension.ASYMMETRIC,
            balance=VisualBalance.LEFT_WEIGHTED,
            rhythm="progressive",
            image_role=ImageRole.DOMINANT,
            typography_role=TypographyRole.EDITORIAL,
            diagram_role="layered",
            white_space=WhiteSpaceStrategy.GENEROUS,
            margins=MarginsStrategy.GENEROUS,
            layering=LayeringStrategy.PRONOUNCED,
            drawing_priority=0.8,
            precision_level="precise",
            annotation_density="moderate",
        )
        assert strategy.focal_point == (0.4, 0.6)
        assert strategy.visual_hierarchy == ["hero_image", "title", "body_text"]
        assert strategy.diagram_role == "layered"
        assert strategy.drawing_priority == 0.8

    def test_drawing_priority_validation(self) -> None:
        """Test drawing_priority must be between 0 and 1."""
        with pytest.raises(ValueError, match="Input should be less than or equal to 1"):
            CompositionStrategy(
                archetype="test",
                dominant_axis=CompositionAxis.VERTICAL,
                reading_path=ReadingPathType.LINEAR_LTR,
                tension=VisualTension.STATIC,
                balance=VisualBalance.CENTERED,
                image_role=ImageRole.EVIDENCE,
                typography_role=TypographyRole.DATA_LABEL,
                white_space=WhiteSpaceStrategy.COMPACT,
                drawing_priority=1.5,  # invalid
            )

    def test_focal_point_can_be_none(self) -> None:
        """Test focal_point is optional and can be None."""
        strategy = CompositionStrategy(
            archetype="data_grid",
            dominant_axis=CompositionAxis.NONE,
            focal_point=None,
            reading_path=ReadingPathType.F_PATTERN,
            tension=VisualTension.SYMMETRIC,
            balance=VisualBalance.CENTERED,
            image_role=ImageRole.ABSENT,
            typography_role=TypographyRole.DATA_LABEL,
            white_space=WhiteSpaceStrategy.COMPACT,
        )
        assert strategy.focal_point is None


class TestCompositionStrategyMethods:
    """Test CompositionStrategy helper methods."""

    def test_is_hero_dominated_true(self) -> None:
        """Test detection of hero-dominated composition."""
        strategy = CompositionStrategy(
            archetype="hero_statement",
            dominant_axis=CompositionAxis.NONE,
            reading_path=ReadingPathType.FOCAL_RADIAL,
            tension=VisualTension.STATIC,
            balance=VisualBalance.CENTERED,
            image_role=ImageRole.DOMINANT,
            typography_role=TypographyRole.HERO,
            white_space=WhiteSpaceStrategy.GENEROUS,
        )
        assert strategy.is_hero_dominated() is True

    def test_is_hero_dominated_false(self) -> None:
        """Test non-hero composition."""
        strategy = CompositionStrategy(
            archetype="data_narrative",
            dominant_axis=CompositionAxis.HORIZONTAL,
            reading_path=ReadingPathType.LINEAR_LTR,
            tension=VisualTension.SYMMETRIC,
            balance=VisualBalance.CENTERED,
            image_role=ImageRole.SUPPORTING,
            typography_role=TypographyRole.DATA_LABEL,
            white_space=WhiteSpaceStrategy.COMPACT,
        )
        assert strategy.is_hero_dominated() is False

    def test_is_editorial_style_true(self) -> None:
        """Test detection of editorial composition."""
        strategy = CompositionStrategy(
            archetype="editorial",
            dominant_axis=CompositionAxis.HORIZONTAL,
            reading_path=ReadingPathType.Z_PATTERN,
            tension=VisualTension.ASYMMETRIC,
            balance=VisualBalance.LEFT_WEIGHTED,
            image_role=ImageRole.DOMINANT,
            typography_role=TypographyRole.EDITORIAL,
            white_space=WhiteSpaceStrategy.BALANCED,
        )
        assert strategy.is_editorial_style() is True

    def test_is_technical_diagram_true(self) -> None:
        """Test detection of technical diagram composition."""
        strategy = CompositionStrategy(
            archetype="technical",
            dominant_axis=CompositionAxis.VERTICAL,
            reading_path=ReadingPathType.F_PATTERN,
            tension=VisualTension.SYMMETRIC,
            balance=VisualBalance.CENTERED,
            image_role=ImageRole.EVIDENCE,
            typography_role=TypographyRole.DATA_LABEL,
            white_space=WhiteSpaceStrategy.BALANCED,
            drawing_priority=0.9,
            layering=LayeringStrategy.FLAT,
        )
        assert strategy.is_technical_diagram() is True

    def test_is_spacious_true(self) -> None:
        """Test detection of spacious composition."""
        strategy = CompositionStrategy(
            archetype="cover",
            dominant_axis=CompositionAxis.NONE,
            reading_path=ReadingPathType.FOCAL_RADIAL,
            tension=VisualTension.STATIC,
            balance=VisualBalance.CENTERED,
            image_role=ImageRole.DOMINANT,
            typography_role=TypographyRole.HERO,
            white_space=WhiteSpaceStrategy.GENEROUS,
            margins=MarginsStrategy.GENEROUS,
        )
        assert strategy.is_spacious() is True

    def test_is_spacious_false(self) -> None:
        """Test non-spacious composition."""
        strategy = CompositionStrategy(
            archetype="data_dense",
            dominant_axis=CompositionAxis.HORIZONTAL,
            reading_path=ReadingPathType.LINEAR_LTR,
            tension=VisualTension.SYMMETRIC,
            balance=VisualBalance.CENTERED,
            image_role=ImageRole.ABSENT,
            typography_role=TypographyRole.DATA_LABEL,
            white_space=WhiteSpaceStrategy.COMPACT,
            margins=MarginsStrategy.TIGHT,
        )
        assert strategy.is_spacious() is False


class TestArchetypePresets:
    """Test predefined composition archetypes."""

    def test_all_presets_are_valid(self) -> None:
        """Test all preset strategies are valid CompositionStrategy instances."""
        for archetype, strategy in ARCHETYPE_PRESETS.items():
            assert isinstance(strategy, CompositionStrategy)
            assert strategy.archetype == archetype

    def test_architectural_editorial_preset(self) -> None:
        """Test architectural_editorial preset has expected characteristics."""
        strategy = ARCHETYPE_PRESETS["architectural_editorial"]
        assert strategy.tension == VisualTension.ASYMMETRIC
        assert strategy.balance == VisualBalance.LEFT_WEIGHTED
        assert strategy.image_role == ImageRole.DOMINANT
        assert strategy.white_space == WhiteSpaceStrategy.GENEROUS
        assert strategy.is_editorial_style() is True

    def test_technical_diagram_preset(self) -> None:
        """Test technical_diagram preset has expected characteristics."""
        strategy = ARCHETYPE_PRESETS["technical_diagram"]
        assert strategy.image_role == ImageRole.EVIDENCE
        assert strategy.typography_role == TypographyRole.DATA_LABEL
        assert strategy.layering == LayeringStrategy.FLAT
        assert strategy.drawing_priority == 0.9
        assert strategy.is_technical_diagram() is True

    def test_hero_statement_preset(self) -> None:
        """Test hero_statement preset has expected characteristics."""
        strategy = ARCHETYPE_PRESETS["hero_statement"]
        assert strategy.balance == VisualBalance.CENTERED
        assert strategy.image_role == ImageRole.DOMINANT
        assert strategy.typography_role == TypographyRole.HERO
        assert strategy.is_hero_dominated() is True
        assert strategy.is_spacious() is True

    def test_get_preset_strategy_exists(self) -> None:
        """Test retrieving existing preset."""
        strategy = get_preset_strategy("data_narrative")
        assert strategy is not None
        assert strategy.archetype == "data_narrative"

    def test_get_preset_strategy_not_exists(self) -> None:
        """Test retrieving non-existent preset returns None."""
        strategy = get_preset_strategy("nonexistent_archetype")
        assert strategy is None


class TestSuggestStrategy:
    """Test heuristic strategy suggestion."""

    def test_suggest_technical_drawing(self) -> None:
        """Test suggestion for technical drawing content."""
        archetype = suggest_strategy_for_content(
            has_large_image=False,
            has_technical_drawing=True,
            has_data_chart=False,
            text_density="moderate",
        )
        assert archetype == "technical_diagram"

    def test_suggest_section_reveal(self) -> None:
        """Test suggestion for section with drawing and image."""
        archetype = suggest_strategy_for_content(
            has_large_image=True,
            has_technical_drawing=True,
            has_data_chart=False,
            text_density="low",
        )
        assert archetype == "section_reveal"

    def test_suggest_data_narrative(self) -> None:
        """Test suggestion for data chart content."""
        archetype = suggest_strategy_for_content(
            has_large_image=False,
            has_technical_drawing=False,
            has_data_chart=True,
            text_density="moderate",
        )
        assert archetype == "data_narrative"

    def test_suggest_hero_statement(self) -> None:
        """Test suggestion for hero image with low text."""
        archetype = suggest_strategy_for_content(
            has_large_image=True,
            has_technical_drawing=False,
            has_data_chart=False,
            text_density="low",
        )
        assert archetype == "hero_statement"

    def test_suggest_architectural_editorial(self) -> None:
        """Test suggestion for image with moderate text."""
        archetype = suggest_strategy_for_content(
            has_large_image=True,
            has_technical_drawing=False,
            has_data_chart=False,
            text_density="moderate",
        )
        assert archetype == "architectural_editorial"

    def test_suggest_default_fallback(self) -> None:
        """Test default fallback when no content matches."""
        archetype = suggest_strategy_for_content(
            has_large_image=False,
            has_technical_drawing=False,
            has_data_chart=False,
            text_density="high",
        )
        assert archetype == "architectural_editorial"


class TestCompositionStrategySerialization:
    """Test JSON serialization and deserialization."""

    def test_serialize_to_dict(self) -> None:
        """Test model can be serialized to dict."""
        strategy = CompositionStrategy(
            archetype="test",
            dominant_axis=CompositionAxis.HORIZONTAL,
            focal_point=(0.5, 0.5),
            reading_path=ReadingPathType.Z_PATTERN,
            tension=VisualTension.ASYMMETRIC,
            balance=VisualBalance.LEFT_WEIGHTED,
            image_role=ImageRole.DOMINANT,
            typography_role=TypographyRole.EDITORIAL,
            white_space=WhiteSpaceStrategy.GENEROUS,
        )
        data = strategy.model_dump()
        assert data["archetype"] == "test"
        assert data["dominant_axis"] == "horizontal"
        assert data["focal_point"] == (0.5, 0.5)

    def test_deserialize_from_dict(self) -> None:
        """Test model can be created from dict."""
        data = {
            "archetype": "test",
            "dominant_axis": "vertical",
            "reading_path": "linear_ltr",
            "tension": "symmetric",
            "balance": "centered",
            "image_role": "supporting",
            "typography_role": "narrative",
            "white_space": "balanced",
        }
        strategy = CompositionStrategy.model_validate(data)
        assert strategy.archetype == "test"
        assert strategy.dominant_axis == CompositionAxis.VERTICAL

    def test_round_trip_serialization(self) -> None:
        """Test serialize and deserialize preserves data."""
        original = ARCHETYPE_PRESETS["architectural_editorial"]
        data = original.model_dump()
        restored = CompositionStrategy.model_validate(data)
        assert restored.archetype == original.archetype
        assert restored.dominant_axis == original.dominant_axis
        assert restored.focal_point == original.focal_point
        assert restored.image_role == original.image_role
