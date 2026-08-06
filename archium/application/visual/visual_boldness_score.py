"""
Visual Boldness Scoring System

Measures the "design courage" of a layout to prevent AI from always generating safe,
symmetric, conventional pages.

High boldness = asymmetric, generous whitespace, strong proportions, visual tension
Low boldness = symmetric, uniform spacing, balanced, predictable

Usage:
    scorer = VisualBoldnessScorer()
    score = scorer.score_layout(layout_plan, composition_strategy)
    # score: 0-100, where 70+ is bold, 30- is safe
"""

from dataclasses import dataclass
from typing import Any

from archium.domain.visual.composition_strategy import (
    CompositionAxis,
    CompositionStrategy,
    ReadingPathType,
    VisualBalance,
    VisualTension,
    WhiteSpaceStrategy,
)
from archium.domain.visual.layout_plan import LayoutElement, LayoutPlan


@dataclass
class BoldnessBreakdown:
    """Detailed breakdown of boldness scoring."""

    proportion_contrast: float  # 0-100: size差异
    asymmetry: float  # 0-100: 非对称程度
    whitespace_strategy: float  # 0-100: 留白战略性
    visual_tension: float  # 0-100: 视觉张力
    hierarchy_clarity: float  # 0-100: 层次清晰度

    overall_score: float  # weighted average

    def to_dict(self) -> dict[str, float]:
        return {
            "proportion_contrast": self.proportion_contrast,
            "asymmetry": self.asymmetry,
            "whitespace_strategy": self.whitespace_strategy,
            "visual_tension": self.visual_tension,
            "hierarchy_clarity": self.hierarchy_clarity,
            "overall_score": self.overall_score,
        }


class VisualBoldnessScorer:
    """
    Scores layout boldness across 5 dimensions.

    Weights:
    - proportion_contrast: 25%
    - asymmetry: 25%
    - whitespace_strategy: 20%
    - visual_tension: 15%
    - hierarchy_clarity: 15%
    """

    def score_layout(
        self,
        layout: LayoutPlan,
        composition: CompositionStrategy | None = None,
    ) -> BoldnessBreakdown:
        """
        Score a layout's visual boldness.

        Args:
            layout: The layout plan to score
            composition: Optional composition strategy (provides intent context)

        Returns:
            BoldnessBreakdown with scores across all dimensions
        """
        elements = layout.elements

        proportion = self._score_proportion_contrast(elements)
        asymmetry = self._score_asymmetry(elements)
        whitespace = self._score_whitespace_strategy(elements, composition)
        tension = self._score_visual_tension(elements, composition)
        hierarchy = self._score_hierarchy_clarity(elements)

        # Weighted average
        overall = (
            proportion * 0.25
            + asymmetry * 0.25
            + whitespace * 0.20
            + tension * 0.15
            + hierarchy * 0.15
        )

        return BoldnessBreakdown(
            proportion_contrast=proportion,
            asymmetry=asymmetry,
            whitespace_strategy=whitespace,
            visual_tension=tension,
            hierarchy_clarity=hierarchy,
            overall_score=overall,
        )

    def _score_proportion_contrast(self, elements: list[LayoutElement]) -> float:
        """
        Measure size差异 between elements.

        Bold: 一个巨大元素 + 多个小元素 (hero image + captions)
        Safe: 所有元素差不多大

        Returns:
            0-100, where 100 = extreme contrast, 0 = uniform
        """
        if len(elements) < 2:
            return 50.0  # neutral for single element

        areas = [el.bounds.width * el.bounds.height for el in elements]
        if not areas or max(areas) == 0:
            return 0.0

        # Calculate coefficient of variation (CV)
        mean_area = sum(areas) / len(areas)
        variance = sum((a - mean_area) ** 2 for a in areas) / len(areas)
        std_dev = variance**0.5
        cv = std_dev / mean_area if mean_area > 0 else 0

        # CV -> 0-100 scale
        # CV = 0: all same size -> 0
        # CV = 1: large variation -> 70
        # CV = 2+: extreme contrast -> 100
        score = min(100.0, cv * 70.0)

        # Bonus for hero-dominated layouts (1 large + many small)
        max_area = max(areas)
        if max_area / mean_area > 3.0:  # largest is 3x average
            score = min(100.0, score + 15.0)

        return score

    def _score_asymmetry(self, elements: list[LayoutElement]) -> float:
        """
        Measure layout asymmetry.

        Bold: elements clustered to one side, uneven distribution
        Safe: symmetric, mirrored, centered

        Returns:
            0-100, where 100 = highly asymmetric, 0 = perfectly symmetric
        """
        if not elements:
            return 0.0

        # Calculate center of mass
        total_area = 0.0
        weighted_x = 0.0
        weighted_y = 0.0

        for el in elements:
            area = el.bounds.width * el.bounds.height
            center_x = el.bounds.x + el.bounds.width / 2
            center_y = el.bounds.y + el.bounds.height / 2

            total_area += area
            weighted_x += center_x * area
            weighted_y += center_y * area

        if total_area == 0:
            return 0.0

        com_x = weighted_x / total_area
        com_y = weighted_y / total_area

        # Distance from slide center (assuming 960x540)
        slide_center_x = 480.0
        slide_center_y = 270.0

        # Normalize distance (0-1 scale, where 1 = extreme edge)
        dx = abs(com_x - slide_center_x) / slide_center_x
        dy = abs(com_y - slide_center_y) / slide_center_y

        # Combined asymmetry
        asymmetry = (dx + dy) / 2

        # Scale to 0-100
        score = min(100.0, asymmetry * 150.0)

        # Bonus for intentional off-center composition
        if dx > 0.3 or dy > 0.3:  # significantly off-center
            score = min(100.0, score + 10.0)

        return score

    def _score_whitespace_strategy(
        self,
        elements: list[LayoutElement],
        composition: CompositionStrategy | None,
    ) -> float:
        """
        Measure strategic whitespace usage.

        Bold: generous, intentional negative space (not just "empty")
        Safe: uniformly distributed elements, minimal gaps

        Returns:
            0-100, where 100 = strategic boldness, 0 = cramped or uniform
        """
        # Total occupied area
        total_element_area = sum(
            el.bounds.width * el.bounds.height for el in elements
        )
        slide_area = 960.0 * 540.0  # standard slide size
        coverage = total_element_area / slide_area if slide_area > 0 else 1.0

        # Base score from coverage
        # 30-50% coverage = bold (lots of breathing room)
        # 70-90% coverage = safe (densely packed)
        if coverage < 0.3:
            base_score = 80.0  # very bold
        elif coverage < 0.5:
            base_score = 60.0  # bold
        elif coverage < 0.7:
            base_score = 40.0  # moderate
        else:
            base_score = 20.0  # safe/crowded

        # Bonus if composition declares generous whitespace strategy
        if composition and composition.white_space == WhiteSpaceStrategy.GENEROUS:
            base_score = min(100.0, base_score + 20.0)
        elif composition and composition.white_space == WhiteSpaceStrategy.MINIMAL:
            base_score = max(0.0, base_score - 20.0)

        return base_score

    def _score_visual_tension(
        self,
        elements: list[LayoutElement],
        composition: CompositionStrategy | None,
    ) -> float:
        """
        Measure visual tension and dynamism.

        Bold: diagonal arrangements, dynamic angles, edge proximity
        Safe: horizontal/vertical alignment, centered, comfortable margins

        Returns:
            0-100, where 100 = high tension, 0 = static
        """
        if not elements:
            return 0.0

        tension_score = 0.0

        # 1. Edge proximity (elements near slide edges)
        edge_elements = 0
        for el in elements:
            if (
                el.bounds.x < 30
                or el.bounds.y < 30
                or (el.bounds.x + el.bounds.width) > 930
                or (el.bounds.y + el.bounds.height) > 510
            ):
                edge_elements += 1

        if elements:
            edge_ratio = edge_elements / len(elements)
            tension_score += edge_ratio * 40.0  # up to 40 points

        # 2. Composition strategy tension
        if composition:
            if composition.tension == VisualTension.HIGH:
                tension_score += 30.0
            elif composition.tension == VisualTension.DYNAMIC:
                tension_score += 20.0
            elif composition.tension == VisualTension.BALANCED:
                tension_score += 10.0
            # CALM adds 0

        # 3. Reading path dynamism
        if composition:
            if composition.reading_path in (
                ReadingPathType.DIAGONAL,
                ReadingPathType.SPIRAL,
                ReadingPathType.SCATTERED,
            ):
                tension_score += 30.0
            elif composition.reading_path == ReadingPathType.Z_PATTERN:
                tension_score += 20.0

        return min(100.0, tension_score)

    def _score_hierarchy_clarity(self, elements: list[LayoutElement]) -> float:
        """
        Measure visual hierarchy clarity.

        Bold: ONE clear dominant element, strong scale relationships
        Safe: multiple competing elements, unclear focus

        Returns:
            0-100, where 100 = crystal clear hierarchy, 0 = flat
        """
        if not elements:
            return 0.0

        areas = [el.bounds.width * el.bounds.height for el in elements]
        if not areas:
            return 0.0

        max_area = max(areas)
        total_area = sum(areas)

        if total_area == 0:
            return 0.0

        # Dominance ratio: largest element as % of total
        dominance = max_area / total_area

        # Score mapping
        # 50%+ = one clear hero (bold)
        # 30-50% = primary + secondary (moderate)
        # <30% = flat hierarchy (safe)
        if dominance > 0.5:
            score = 85.0 + (dominance - 0.5) * 30.0  # 85-100
        elif dominance > 0.3:
            score = 50.0 + (dominance - 0.3) * 175.0  # 50-85
        else:
            score = dominance * 166.67  # 0-50

        return min(100.0, score)


def score_boldness(
    layout: LayoutPlan,
    composition: CompositionStrategy | None = None,
) -> float:
    """
    Convenience function to get overall boldness score.

    Args:
        layout: The layout plan to score
        composition: Optional composition strategy

    Returns:
        Overall boldness score (0-100)
    """
    scorer = VisualBoldnessScorer()
    breakdown = scorer.score_layout(layout, composition)
    return breakdown.overall_score
