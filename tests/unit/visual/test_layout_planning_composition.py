"""Tests for PageType + CompositionStrategy integration in layout planning."""

import pytest
from uuid import uuid4

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
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.page_type import PageType
from archium.infrastructure.layout.layout_family_registry import (
    LayoutFamilyRegistry,
    get_layout_family_registry,
)


class TestLayoutFamilyRegistryComposition:
    """Test LayoutFamilyRegistry.candidates_for_composition()."""

    def test_hero_dominated_strategy_selects_hero_family(self) -> None:
        """Test hero-dominated composition selects HERO family."""
        registry = get_layout_family_registry()

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

        candidates = registry.candidates_for_composition(
            page_type="cover",
            composition_strategy=strategy,
            asset_count=1,
        )

        assert len(candidates) >= 1
        assert candidates[0].family == LayoutFamily.HERO

    def test_technical_diagram_high_drawing_priority_selects_drawing_focus(self) -> None:
        """Test technical diagram with high drawing priority selects DRAWING_FOCUS."""
        registry = get_layout_family_registry()

        strategy = CompositionStrategy(
            archetype="technical_diagram",
            dominant_axis=CompositionAxis.VERTICAL,
            reading_path=ReadingPathType.F_PATTERN,
            tension=VisualTension.SYMMETRIC,
            balance=VisualBalance.CENTERED,
            image_role=ImageRole.EVIDENCE,
            typography_role=TypographyRole.DATA_LABEL,
            white_space=WhiteSpaceStrategy.BALANCED,
            drawing_priority=0.9,
        )

        candidates = registry.candidates_for_composition(
            page_type="technical_drawing",
            composition_strategy=strategy,
            asset_count=1,
        )

        assert len(candidates) >= 1
        assert candidates[0].family == LayoutFamily.DRAWING_FOCUS

    def test_evidence_role_with_multiple_assets_selects_evidence_board(self) -> None:
        """Test evidence role with multiple assets selects EVIDENCE_BOARD."""
        registry = get_layout_family_registry()

        strategy = CompositionStrategy(
            archetype="architectural_editorial",
            dominant_axis=CompositionAxis.HORIZONTAL,
            reading_path=ReadingPathType.Z_PATTERN,
            tension=VisualTension.ASYMMETRIC,
            balance=VisualBalance.LEFT_WEIGHTED,
            image_role=ImageRole.EVIDENCE,
            typography_role=TypographyRole.EDITORIAL,
            white_space=WhiteSpaceStrategy.BALANCED,
        )

        candidates = registry.candidates_for_composition(
            page_type="evidence",
            composition_strategy=strategy,
            asset_count=3,
        )

        assert len(candidates) >= 1
        assert candidates[0].family in (
            LayoutFamily.EVIDENCE_BOARD,
            LayoutFamily.COMPARATIVE_MATRIX,
        )

    def test_absent_image_role_selects_text_families(self) -> None:
        """Test absent image role selects text-focused families."""
        registry = get_layout_family_registry()

        strategy = CompositionStrategy(
            archetype="textual_argument",
            dominant_axis=CompositionAxis.VERTICAL,
            reading_path=ReadingPathType.LINEAR_LTR,
            tension=VisualTension.SYMMETRIC,
            balance=VisualBalance.CENTERED,
            image_role=ImageRole.ABSENT,
            typography_role=TypographyRole.NARRATIVE,
            white_space=WhiteSpaceStrategy.BALANCED,
        )

        candidates = registry.candidates_for_composition(
            page_type="text_argument",
            composition_strategy=strategy,
            asset_count=0,
        )

        assert len(candidates) >= 1
        assert candidates[0].family in (
            LayoutFamily.TEXTUAL_ARGUMENT,
            LayoutFamily.STRATEGY_CARDS,
        )

    def test_editorial_style_with_assets_selects_hybrid_or_evidence(self) -> None:
        """Test editorial style with assets selects HYBRID_CANVAS or EVIDENCE_BOARD."""
        registry = get_layout_family_registry()

        strategy = CompositionStrategy(
            archetype="architectural_editorial",
            dominant_axis=CompositionAxis.HORIZONTAL,
            reading_path=ReadingPathType.Z_PATTERN,
            tension=VisualTension.ASYMMETRIC,
            balance=VisualBalance.LEFT_WEIGHTED,
            image_role=ImageRole.SUPPORTING,
            typography_role=TypographyRole.EDITORIAL,
            white_space=WhiteSpaceStrategy.GENEROUS,
        )

        candidates = registry.candidates_for_composition(
            page_type="strategy",
            composition_strategy=strategy,
            asset_count=2,
        )

        assert len(candidates) >= 1
        # Should select families that support editorial + multiple assets
        assert candidates[0].family in (
            LayoutFamily.HYBRID_CANVAS,
            LayoutFamily.EVIDENCE_BOARD,
        )

    def test_fallback_to_page_type_hints_when_no_composition_match(self) -> None:
        """Test fallback to PageType hints when composition doesn't match strongly."""
        registry = get_layout_family_registry()

        # Strategy that doesn't trigger strong rules
        strategy = CompositionStrategy(
            archetype="custom",
            dominant_axis=CompositionAxis.HORIZONTAL,
            reading_path=ReadingPathType.LINEAR_LTR,
            tension=VisualTension.SYMMETRIC,
            balance=VisualBalance.CENTERED,
            image_role=ImageRole.SUPPORTING,
            typography_role=TypographyRole.NARRATIVE,
            white_space=WhiteSpaceStrategy.BALANCED,
            drawing_priority=0.3,
        )

        candidates = registry.candidates_for_composition(
            page_type="strategy",
            composition_strategy=strategy,
            asset_count=1,
        )

        assert len(candidates) >= 1
        # Should use PageType hints (STRATEGY → STRATEGY_CARDS, TEXTUAL_ARGUMENT)
        family_values = [c.family for c in candidates]
        assert any(
            f in family_values
            for f in [
                LayoutFamily.STRATEGY_CARDS,
                LayoutFamily.TEXTUAL_ARGUMENT,
                LayoutFamily.HERO,
            ]
        )

    def test_legacy_path_with_string_composition_strategy(self) -> None:
        """Test backward compatibility with string composition_strategy."""
        registry = get_layout_family_registry()

        candidates = registry.candidates_for_composition(
            page_type="strategy",
            composition_strategy="use hero layout with large image",  # legacy string
            asset_count=1,
        )

        # Should fall back gracefully
        assert len(candidates) >= 1

    def test_no_page_type_falls_back_to_content_matching(self) -> None:
        """Test fallback when page_type is None."""
        registry = get_layout_family_registry()

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

        candidates = registry.candidates_for_composition(
            page_type=None,
            composition_strategy=strategy,
            asset_count=1,
        )

        # Should still work via composition-driven selection
        assert len(candidates) >= 1


class TestCompositionStrategyIntegration:
    """Integration tests for full PageType + CompositionStrategy flow."""

    def test_same_page_type_different_strategies_yield_different_families(self) -> None:
        """Test same PageType with different strategies yields different families."""
        registry = get_layout_family_registry()
        page_type = "strategy"
        asset_count = 1

        # Strategy 1: Hero-dominated (BIG style)
        big_strategy = CompositionStrategy(
            archetype="hero_statement",
            dominant_axis=CompositionAxis.NONE,
            reading_path=ReadingPathType.FOCAL_RADIAL,
            tension=VisualTension.DYNAMIC,
            balance=VisualBalance.CENTERED,
            image_role=ImageRole.DOMINANT,
            typography_role=TypographyRole.HERO,
            white_space=WhiteSpaceStrategy.GENEROUS,
        )

        # Strategy 2: Editorial (SOM style)
        som_strategy = CompositionStrategy(
            archetype="architectural_editorial",
            dominant_axis=CompositionAxis.HORIZONTAL,
            reading_path=ReadingPathType.Z_PATTERN,
            tension=VisualTension.ASYMMETRIC,
            balance=VisualBalance.LEFT_WEIGHTED,
            image_role=ImageRole.SUPPORTING,
            typography_role=TypographyRole.EDITORIAL,
            white_space=WhiteSpaceStrategy.GENEROUS,
        )

        big_candidates = registry.candidates_for_composition(
            page_type=page_type,
            composition_strategy=big_strategy,
            asset_count=asset_count,
        )

        som_candidates = registry.candidates_for_composition(
            page_type=page_type,
            composition_strategy=som_strategy,
            asset_count=asset_count,
        )

        # Should select different primary families
        assert big_candidates[0].family == LayoutFamily.HERO
        assert som_candidates[0].family in (
            LayoutFamily.HYBRID_CANVAS,
            LayoutFamily.EVIDENCE_BOARD,
        )
