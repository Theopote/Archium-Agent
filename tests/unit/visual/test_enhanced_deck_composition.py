"""Tests for Enhanced Deck Composition Service."""

import pytest
from uuid import uuid4

from archium.application.visual.enhanced_deck_composition_service import (
    EnhancedDeckCompositionService,
    FeedbackSemanticParser,
    VisualIntensityAnalyzer,
    PatternRecognizer,
    DeckQAAnalyzer,
)
from archium.domain.visual.deck_composition import (
    SlideCompositionDirective,
    VisualIntensity,
    DensityLevel,
    PacingRole,
)
from archium.domain.visual.enums import LayoutFamily


class TestFeedbackSemanticParser:
    """Test feedback parsing."""

    def test_parse_monotonous_rhythm(self):
        parser = FeedbackSemanticParser(llm_provider=None)
        result = parser.parse("节奏太单调，需要更多变化")

        assert result.problem_type == "monotonous_rhythm"
        assert result.desired_direction == "increase_contrast"
        assert result.severity in ["minor", "moderate", "severe"]

    def test_parse_weak_hero(self):
        parser = FeedbackSemanticParser(llm_provider=None)
        result = parser.parse("主图不够突出，视觉冲击力不足")

        assert result.problem_type == "weak_hero"
        assert result.desired_direction == "enhance_hero"

    def test_parse_specific_pages(self):
        parser = FeedbackSemanticParser(llm_provider=None)
        result = parser.parse("第3页和第5页文字太多")

        assert result.problem_type == "excessive_text"
        assert result.specific_pages == [2, 4]  # 0-indexed

    def test_parse_severity_indicators(self):
        parser = FeedbackSemanticParser(llm_provider=None)

        minor = parser.parse("稍微有点单调")
        assert minor.severity == "minor"
        assert minor.adjustment_magnitude < 0.5

        severe = parser.parse("非常单调，太无聊了")
        assert severe.severity == "severe"
        assert severe.adjustment_magnitude > 0.6


class TestVisualIntensityAnalyzer:
    """Test visual intensity analysis."""

    def test_monotonic_detection(self):
        # Create directives with monotonic region
        directives = [
            self._make_directive(i, VisualIntensity.MEDIUM)
            for i in range(8)
        ]

        analyzer = VisualIntensityAnalyzer()
        curve = analyzer.analyze(directives)

        assert len(curve.monotonic_spans) > 0
        assert curve.smoothness > 0.8  # Very smooth = monotonic

    def test_peak_valley_detection(self):
        intensities = [
            VisualIntensity.LOW,
            VisualIntensity.MEDIUM,
            VisualIntensity.HIGH,  # Peak
            VisualIntensity.MEDIUM,
            VisualIntensity.LOW,  # Valley
            VisualIntensity.MEDIUM,
        ]
        directives = [
            self._make_directive(i, intensity)
            for i, intensity in enumerate(intensities)
        ]

        analyzer = VisualIntensityAnalyzer()
        curve = analyzer.analyze(directives)

        assert 2 in curve.peaks  # Index 2 is peak
        assert 4 in curve.valleys  # Index 4 is valley

    def test_variance_calculation(self):
        # High variance
        varied = [
            self._make_directive(i, VisualIntensity.HIGH if i % 2 else VisualIntensity.LOW)
            for i in range(6)
        ]

        # Low variance
        uniform = [
            self._make_directive(i, VisualIntensity.MEDIUM)
            for i in range(6)
        ]

        analyzer = VisualIntensityAnalyzer()
        varied_curve = analyzer.analyze(varied)
        uniform_curve = analyzer.analyze(uniform)

        assert varied_curve.variance > uniform_curve.variance

    def _make_directive(self, index: int, intensity: VisualIntensity):
        return SlideCompositionDirective(
            slide_id=uuid4(),
            slide_index=index,
            narrative_role=f"slide_{index}",
            pacing_role=PacingRole.SETUP,
            visual_intensity=intensity,
            target_density=DensityLevel.MODERATE,
            preferred_layout_families=[LayoutFamily.HERO],
            hero_priority=0.5,
            text_priority=0.5,
            drawing_priority=0.3,
        )


class TestPatternRecognizer:
    """Test pattern recognition."""

    def test_monotonous_rhythm_pattern(self):
        # Create monotonic directives
        directives = [
            self._make_directive(i, VisualIntensity.MEDIUM)
            for i in range(10)
        ]

        analyzer = VisualIntensityAnalyzer()
        curve = analyzer.analyze(directives)

        recognizer = PatternRecognizer()
        patterns = recognizer.recognize(directives, curve, self._empty_qa())

        monotonic_patterns = [
            p for p in patterns if p.pattern_type == "monotonous_rhythm"
        ]
        assert len(monotonic_patterns) > 0

    def test_excessive_repetition_pattern(self):
        # Create directives with family repetition
        directives = [
            self._make_directive(i, VisualIntensity.MEDIUM, LayoutFamily.HERO)
            for i in range(6)
        ]

        analyzer = VisualIntensityAnalyzer()
        curve = analyzer.analyze(directives)

        recognizer = PatternRecognizer()
        patterns = recognizer.recognize(directives, curve, self._empty_qa())

        repetition_patterns = [
            p for p in patterns if p.pattern_type == "excessive_repetition"
        ]
        assert len(repetition_patterns) > 0

    def test_low_variance_pattern(self):
        directives = [
            self._make_directive(i, VisualIntensity.MEDIUM)
            for i in range(5)
        ]

        analyzer = VisualIntensityAnalyzer()
        curve = analyzer.analyze(directives)

        recognizer = PatternRecognizer()
        patterns = recognizer.recognize(directives, curve, self._empty_qa())

        assert any(p.pattern_type == "low_variance" for p in patterns)

    def _make_directive(
        self,
        index: int,
        intensity: VisualIntensity,
        family: LayoutFamily = LayoutFamily.HERO,
    ):
        return SlideCompositionDirective(
            slide_id=uuid4(),
            slide_index=index,
            narrative_role=f"slide_{index}",
            pacing_role=PacingRole.SETUP,
            visual_intensity=intensity,
            target_density=DensityLevel.MODERATE,
            preferred_layout_families=[family],
            hero_priority=0.5,
            text_priority=0.5,
            drawing_priority=0.3,
        )

    def _empty_qa(self):
        from archium.application.visual.enhanced_deck_composition_service import (
            DeckQAContext,
        )
        return DeckQAContext(
            critical_issues=[],
            moderate_issues=[],
            affected_slide_indices=[],
            consistency_score=1.0,
            variety_score=1.0,
        )


class TestEnhancedDeckCompositionService:
    """Test the enhanced service."""

    def test_enhanced_revision_with_monotonous_feedback(self):
        # This would require full setup with slides, intents, etc.
        # Placeholder for integration test
        pass

    def test_targeted_adjustments(self):
        # Test that adjustments are applied correctly
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
