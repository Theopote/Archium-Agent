"""
Tests for Visual Boldness Scoring System
"""

import pytest

from archium.application.visual.visual_boldness_score import (
    VisualBoldnessScorer,
    score_boldness,
)
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
from archium.domain.visual.layout_plan import Bounds, LayoutElement, LayoutPlan


def create_test_layout(elements: list[tuple[float, float, float, float]]) -> LayoutPlan:
    """
    Create a test layout from element bounds.

    Args:
        elements: List of (x, y, width, height) tuples
    """
    layout_elements = [
        LayoutElement(
            id=f"elem_{i}",
            role="text",
            bounds=Bounds(x=x, y=y, width=w, height=h),
        )
        for i, (x, y, w, h) in enumerate(elements)
    ]

    return LayoutPlan(
        id="test-plan",
        layout_family="hero",
        elements=layout_elements,
    )


class TestProportionContrast:
    """Test proportion contrast scoring."""

    def test_uniform_sizes_low_score(self):
        """All same-size elements should score low (safe)."""
        layout = create_test_layout([
            (50, 50, 100, 100),
            (200, 50, 100, 100),
            (350, 50, 100, 100),
        ])

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout)

        # Uniform sizes = low proportion contrast
        assert breakdown.proportion_contrast < 30.0

    def test_hero_dominated_high_score(self):
        """One large element + small elements = high score (bold)."""
        layout = create_test_layout([
            (50, 50, 700, 400),    # Hero
            (50, 460, 100, 50),    # Caption 1
            (160, 460, 100, 50),   # Caption 2
            (270, 460, 100, 50),   # Caption 3
        ])

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout)

        # Hero-dominated = high proportion contrast
        assert breakdown.proportion_contrast > 70.0

    def test_single_element_neutral(self):
        """Single element should return neutral score."""
        layout = create_test_layout([
            (100, 100, 500, 300),
        ])

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout)

        assert breakdown.proportion_contrast == 50.0


class TestAsymmetry:
    """Test asymmetry scoring."""

    def test_centered_layout_low_score(self):
        """Centered layout = low asymmetry (safe)."""
        layout = create_test_layout([
            (380, 220, 200, 100),  # Centered on 960x540 slide
        ])

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout)

        # Centered = low asymmetry
        assert breakdown.asymmetry < 30.0

    def test_edge_clustered_high_score(self):
        """Elements clustered to one side = high asymmetry (bold)."""
        layout = create_test_layout([
            (50, 50, 300, 200),
            (50, 270, 300, 200),
        ])

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout)

        # Left-clustered = high asymmetry
        assert breakdown.asymmetry > 50.0

    def test_symmetric_grid_low_score(self):
        """Symmetric grid = low asymmetry."""
        layout = create_test_layout([
            (100, 100, 200, 150),
            (660, 100, 200, 150),
            (100, 290, 200, 150),
            (660, 290, 200, 150),
        ])

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout)

        # Symmetric = low asymmetry
        assert breakdown.asymmetry < 40.0


class TestWhitespaceStrategy:
    """Test whitespace strategy scoring."""

    def test_generous_whitespace_high_score(self):
        """Low coverage with generous strategy = high score (bold)."""
        layout = create_test_layout([
            (200, 150, 300, 150),  # ~8% coverage
        ])

        composition = CompositionStrategy(
            archetype="hero_statement",
            dominant_axis=CompositionAxis.HORIZONTAL,
            reading_path=ReadingPathType.DIRECT,
            tension=VisualTension.CALM,
            balance=VisualBalance.ASYMMETRIC,
            image_role=ImageRole.HERO,
            typography_role=TypographyRole.SUPPORTING,
            white_space=WhiteSpaceStrategy.GENEROUS,
        )

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout, composition)

        # Generous whitespace + low coverage = high score
        assert breakdown.whitespace_strategy > 80.0

    def test_crowded_layout_low_score(self):
        """High coverage = low score (safe/crowded)."""
        layout = create_test_layout([
            (50, 50, 400, 200),
            (50, 260, 400, 200),
            (460, 50, 400, 200),
            (460, 260, 400, 200),
        ])

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout)

        # High coverage = low whitespace score
        assert breakdown.whitespace_strategy < 40.0


class TestVisualTension:
    """Test visual tension scoring."""

    def test_high_tension_composition(self):
        """High tension strategy = high tension score (bold)."""
        layout = create_test_layout([
            (10, 10, 300, 200),  # Edge proximity
            (650, 330, 300, 200),  # Edge proximity
        ])

        composition = CompositionStrategy(
            archetype="architectural_editorial",
            dominant_axis=CompositionAxis.DIAGONAL,
            reading_path=ReadingPathType.DIAGONAL,
            tension=VisualTension.HIGH,
            balance=VisualBalance.ASYMMETRIC,
            image_role=ImageRole.HERO,
            typography_role=TypographyRole.SUPPORTING,
            white_space=WhiteSpaceStrategy.STRATEGIC,
        )

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout, composition)

        # High tension + edge elements + diagonal reading = high score
        assert breakdown.visual_tension > 70.0

    def test_calm_centered_layout(self):
        """Calm composition with centered elements = low tension (safe)."""
        layout = create_test_layout([
            (330, 195, 300, 150),  # Centered, comfortable margins
        ])

        composition = CompositionStrategy(
            archetype="hero_statement",
            dominant_axis=CompositionAxis.HORIZONTAL,
            reading_path=ReadingPathType.DIRECT,
            tension=VisualTension.CALM,
            balance=VisualBalance.SYMMETRIC,
            image_role=ImageRole.HERO,
            typography_role=TypographyRole.SUPPORTING,
            white_space=WhiteSpaceStrategy.GENEROUS,
        )

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout, composition)

        # Calm + centered = low tension
        assert breakdown.visual_tension < 40.0


class TestHierarchyClarity:
    """Test hierarchy clarity scoring."""

    def test_clear_hero_high_score(self):
        """One dominant element = high hierarchy clarity (bold)."""
        layout = create_test_layout([
            (100, 100, 600, 300),  # Hero (180k sq units)
            (100, 420, 100, 50),   # Caption (5k sq units)
            (220, 420, 100, 50),
        ])

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout)

        # Clear dominant element = high hierarchy
        assert breakdown.hierarchy_clarity > 80.0

    def test_flat_hierarchy_low_score(self):
        """Many equal-sized elements = low hierarchy (safe)."""
        layout = create_test_layout([
            (100, 100, 150, 150),
            (270, 100, 150, 150),
            (440, 100, 150, 150),
            (610, 100, 150, 150),
        ])

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout)

        # Flat hierarchy = low score
        assert breakdown.hierarchy_clarity < 50.0


class TestOverallScore:
    """Test overall boldness scoring."""

    def test_bold_layout_high_score(self):
        """Bold design characteristics = high overall score."""
        # Asymmetric, hero-dominated, generous whitespace, edge proximity
        layout = create_test_layout([
            (50, 50, 500, 400),    # Hero at edge
            (600, 470, 300, 50),   # Small caption at opposite edge
        ])

        composition = CompositionStrategy(
            archetype="architectural_editorial",
            dominant_axis=CompositionAxis.DIAGONAL,
            reading_path=ReadingPathType.DIAGONAL,
            tension=VisualTension.HIGH,
            balance=VisualBalance.ASYMMETRIC,
            image_role=ImageRole.HERO,
            typography_role=TypographyRole.ACCENT,
            white_space=WhiteSpaceStrategy.GENEROUS,
        )

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout, composition)

        # Bold characteristics = high overall score
        assert breakdown.overall_score > 70.0

    def test_safe_layout_low_score(self):
        """Safe/conventional design = low overall score."""
        # Centered, uniform, symmetric, predictable
        layout = create_test_layout([
            (240, 140, 200, 120),
            (520, 140, 200, 120),
            (240, 280, 200, 120),
            (520, 280, 200, 120),
        ])

        composition = CompositionStrategy(
            archetype="data_narrative",
            dominant_axis=CompositionAxis.GRID,
            reading_path=ReadingPathType.Z_PATTERN,
            tension=VisualTension.BALANCED,
            balance=VisualBalance.SYMMETRIC,
            image_role=ImageRole.SUPPORTING,
            typography_role=TypographyRole.PRIMARY,
            white_space=WhiteSpaceStrategy.BALANCED,
        )

        scorer = VisualBoldnessScorer()
        breakdown = scorer.score_layout(layout, composition)

        # Safe characteristics = low overall score
        assert breakdown.overall_score < 50.0

    def test_convenience_function(self):
        """Test convenience function."""
        layout = create_test_layout([
            (100, 100, 600, 300),
            (100, 420, 100, 50),
        ])

        score = score_boldness(layout)

        # Should return a valid score
        assert 0.0 <= score <= 100.0
