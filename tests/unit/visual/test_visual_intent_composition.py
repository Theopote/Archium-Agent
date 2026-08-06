"""Tests for VisualIntent with CompositionStrategy integration."""

import pytest

from archium.domain.visual.composition_strategy import (
    CompositionAxis,
    CompositionStrategy,
    ImageRole,
    ReadingPathType,
    TypographyRole,
    VisualBalance,
    VisualTension,
    WhiteSpaceStrategy,
)
from archium.domain.visual.enums import ContinuityRole, DensityLevel, LayoutFamily, VisualContentType
from archium.domain.visual.visual_intent import VisualIntent


class TestVisualIntentCompositionStrategy:
    """Test VisualIntent integration with CompositionStrategy."""

    def test_visual_intent_with_structured_composition(self, base_slide_id: str) -> None:
        """Test VisualIntent can hold structured CompositionStrategy."""
        strategy = CompositionStrategy(
            archetype="architectural_editorial",
            dominant_axis=CompositionAxis.HORIZONTAL,
            reading_path=ReadingPathType.Z_PATTERN,
            tension=VisualTension.ASYMMETRIC,
            balance=VisualBalance.LEFT_WEIGHTED,
            image_role=ImageRole.DOMINANT,
            typography_role=TypographyRole.EDITORIAL,
            white_space=WhiteSpaceStrategy.GENEROUS,
        )

        intent = VisualIntent(
            slide_id=base_slide_id,
            communication_goal="Show project context",
            audience_takeaway="Understand site constraints",
            visual_priority="Site plan dominance",
            dominant_content_type=VisualContentType.IMAGE,
            composition_strategy=strategy,
        )

        assert intent.has_structured_composition() is True
        retrieved = intent.get_composition_strategy()
        assert retrieved is not None
        assert retrieved.archetype == "architectural_editorial"

    def test_visual_intent_with_legacy_string_composition(self, base_slide_id: str) -> None:
        """Test backward compatibility with string composition_strategy."""
        intent = VisualIntent(
            slide_id=base_slide_id,
            communication_goal="Show analysis",
            audience_takeaway="Understand issues",
            visual_priority="Text clarity",
            dominant_content_type=VisualContentType.TEXT,
            composition_strategy="Use left-weighted layout with large margins",
        )

        assert intent.has_structured_composition() is False
        assert intent.composition_strategy == "Use left-weighted layout with large margins"
        assert intent.get_composition_strategy() is None

    def test_visual_intent_composition_strategy_none(self, base_slide_id: str) -> None:
        """Test VisualIntent with no composition_strategy set."""
        intent = VisualIntent(
            slide_id=base_slide_id,
            communication_goal="Basic slide",
            audience_takeaway="Simple message",
            visual_priority="Title",
            dominant_content_type=VisualContentType.TEXT,
            composition_strategy=None,
        )

        assert intent.has_structured_composition() is False
        assert intent.get_composition_strategy() is None

    def test_visual_intent_coerce_dict_to_composition_strategy(self, base_slide_id: str) -> None:
        """Test validator coerces dict to CompositionStrategy."""
        intent = VisualIntent(
            slide_id=base_slide_id,
            communication_goal="Test",
            audience_takeaway="Test",
            visual_priority="Test",
            dominant_content_type=VisualContentType.IMAGE,
            composition_strategy={
                "archetype": "hero_statement",
                "dominant_axis": "none",
                "reading_path": "focal_radial",
                "tension": "static",
                "balance": "centered",
                "image_role": "dominant",
                "typography_role": "hero",
                "white_space": "generous",
            },
        )

        assert intent.has_structured_composition() is True
        strategy = intent.get_composition_strategy()
        assert strategy is not None
        assert strategy.archetype == "hero_statement"

    def test_visual_intent_serialization_with_composition_strategy(self, base_slide_id: str) -> None:
        """Test VisualIntent with CompositionStrategy serializes correctly."""
        strategy = CompositionStrategy(
            archetype="technical_diagram",
            dominant_axis=CompositionAxis.VERTICAL,
            reading_path=ReadingPathType.F_PATTERN,
            tension=VisualTension.SYMMETRIC,
            balance=VisualBalance.CENTERED,
            image_role=ImageRole.EVIDENCE,
            typography_role=TypographyRole.DATA_LABEL,
            white_space=WhiteSpaceStrategy.BALANCED,
        )

        intent = VisualIntent(
            slide_id=base_slide_id,
            communication_goal="Technical analysis",
            audience_takeaway="Understand dimensions",
            visual_priority="Diagram clarity",
            dominant_content_type=VisualContentType.DIAGRAM,
            composition_strategy=strategy,
        )

        # Serialize
        data = intent.model_dump()
        assert isinstance(data["composition_strategy"], dict)
        assert data["composition_strategy"]["archetype"] == "technical_diagram"

        # Deserialize
        restored = VisualIntent.model_validate(data)
        assert restored.has_structured_composition() is True
        restored_strategy = restored.get_composition_strategy()
        assert restored_strategy is not None
        assert restored_strategy.archetype == "technical_diagram"
        assert restored_strategy.dominant_axis == CompositionAxis.VERTICAL


@pytest.fixture
def base_slide_id() -> str:
    """Fixture providing a UUID for slide_id."""
    from uuid import uuid4

    return str(uuid4())
