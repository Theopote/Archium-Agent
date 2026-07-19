"""Enhanced Deck Composition Planning with multi-dimensional analysis.

This module extends the base DeckCompositionPlanningService with:
1. DeckQA feedback integration
2. LLM-based feedback semantic understanding
3. Visual intensity curve analysis
4. Section semantic analysis
5. Pattern recognition
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel

# Import base service
from archium.application.visual.deck_composition_service import (
    DeckCompositionPlanningService,
)
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.deck_composition import (
    DeckCompositionPlan,
    SlideCompositionDirective,
    VisualIntensity,
    density_to_score,
    intensity_to_score,
)
from archium.domain.visual.deck_qa import DeckQAReport, LayoutIssueSeverity
from archium.domain.visual.enums import DensityLevel
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.llm.base import LLMRequest
from archium.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class FeedbackIntent:
    """Structured understanding of user feedback."""

    problem_type: str  # "monotonous_rhythm", "weak_hero", "inconsistent_chrome"
    severity: str  # "minor", "moderate", "severe"
    scope: str  # "global", "section:1", "slides:3,5,7"
    desired_direction: str  # "increase_contrast", "enhance_hero"
    adjustment_magnitude: float  # 0.1-1.0
    specific_pages: list[int] | None = None


class _FeedbackIntentDraft(BaseModel):
    """Structured output schema for LLM feedback parsing."""

    problem_type: str = "general"
    severity: str = "moderate"
    scope: str = "global"
    desired_direction: str = "improve_overall"
    adjustment_magnitude: float = 0.5
    specific_pages: list[int] | None = None


@dataclass(frozen=True)
class DeckQAContext:
    """Extracted context from DeckQA report."""

    critical_issues: list[str]
    moderate_issues: list[str]
    affected_slide_indices: list[int]
    consistency_score: float
    variety_score: float


@dataclass(frozen=True)
class VisualIntensityCurve:
    """Analysis of visual intensity distribution."""

    scores: list[float]
    smoothness: float
    variance: float
    monotonic_spans: list[tuple[int, int]]  # (start, end) of flat regions
    peaks: list[int]
    valleys: list[int]


@dataclass(frozen=True)
class RecognizedPattern:
    """A detected pattern that needs correction."""

    pattern_type: str
    severity: str
    affected_indices: list[int]
    description: str
    suggested_fix: str
    confidence: float = 0.8


class DeckQAAnalyzer:
    """Extract actionable insights from DeckQA report."""

    def analyze(self, report: DeckQAReport | None) -> DeckQAContext:
        if report is None or not report.findings:
            return DeckQAContext(
                critical_issues=[],
                moderate_issues=[],
                affected_slide_indices=[],
                consistency_score=1.0,
                variety_score=1.0,
            )

        critical = []
        moderate = []
        affected_indices = set()

        for finding in report.findings:
            desc = f"{finding.dimension}: {finding.message}"
            if finding.severity == LayoutIssueSeverity.CRITICAL:
                critical.append(desc)
            elif finding.severity == LayoutIssueSeverity.ERROR:
                moderate.append(desc)

            # Extract affected slide indices if available
            # (Assuming findings have slide_indices attribute)
            if hasattr(finding, "slide_indices"):
                affected_indices.update(finding.slide_indices)

        return DeckQAContext(
            critical_issues=critical,
            moderate_issues=moderate,
            affected_slide_indices=sorted(affected_indices),
            consistency_score=getattr(report, "consistency_score", 0.8),
            variety_score=getattr(report, "variety_score", 0.8),
        )


class FeedbackSemanticParser:
    """Parse user feedback into structured intent using LLM."""

    def __init__(self, llm_provider=None):
        self._llm = llm_provider

    def parse(self, feedback: str) -> FeedbackIntent:
        """Parse feedback into structured intent."""
        if self._llm is None:
            # Fallback to enhanced keyword matching
            return self._parse_with_keywords(feedback)

        # Use LLM for semantic understanding
        return self._parse_with_llm(feedback)

    def _parse_with_keywords(self, feedback: str) -> FeedbackIntent:
        """Enhanced keyword-based parsing (fallback)."""
        normalized = feedback.strip().lower()

        # Detect problem type
        if any(w in normalized for w in ["节奏", "单调", "rhythm", "monotonous"]):
            problem_type = "monotonous_rhythm"
            desired = "increase_contrast"
        elif any(w in normalized for w in ["主图", "hero", "视觉", "图片"]):
            problem_type = "weak_hero"
            desired = "enhance_hero"
        elif any(w in normalized for w in ["文字", "密度", "text", "density"]):
            problem_type = "excessive_text"
            desired = "reduce_density"
        elif any(w in normalized for w in ["不一致", "inconsistent", "统一"]):
            problem_type = "inconsistent_chrome"
            desired = "unify_layout"
        else:
            problem_type = "general"
            desired = "improve_overall"

        # Detect severity
        if any(w in normalized for w in ["严重", "非常", "太", "very", "too"]):
            severity = "severe"
            magnitude = 0.8
        elif any(w in normalized for w in ["有点", "稍", "略", "slightly"]):
            severity = "minor"
            magnitude = 0.3
        else:
            severity = "moderate"
            magnitude = 0.5

        # Detect scope
        scope = "global"
        specific_pages = None

        # Try to extract specific page numbers
        import re

        page_match = re.findall(r"第?(\d+)页", normalized)
        if page_match:
            specific_pages = [int(p) - 1 for p in page_match]  # Convert to 0-indexed
            scope = f"slides:{','.join(page_match)}"

        return FeedbackIntent(
            problem_type=problem_type,
            severity=severity,
            scope=scope,
            desired_direction=desired,
            adjustment_magnitude=magnitude,
            specific_pages=specific_pages,
        )

    def _parse_with_llm(self, feedback: str) -> FeedbackIntent:
        """Use LLM to understand feedback semantics."""
        prompt = f"""解析用户对演示文稿的反馈，返回 JSON：

反馈: "{feedback}"

返回格式：
{{
  "problem_type": "monotonous_rhythm|weak_hero|excessive_text|inconsistent_chrome|general",
  "severity": "minor|moderate|severe",
  "scope": "global|section:1|slides:3,5,7",
  "desired_direction": "具体改进方向",
  "adjustment_magnitude": 0.1-1.0,
  "specific_pages": [page_numbers] or null
}}
"""
        request = LLMRequest(
            system_prompt="你是演示文稿用户反馈的语义解析器，只返回符合要求格式的 JSON。",
            user_prompt=prompt,
            temperature=0.1,
            json_mode=True,
        )
        try:
            draft = self._llm.generate_structured(request, _FeedbackIntentDraft)
            return FeedbackIntent(**draft.model_dump())
        except Exception as exc:
            logger.warning("LLM feedback parsing failed, falling back to keywords: %s", exc)
            return self._parse_with_keywords(feedback)


class VisualIntensityAnalyzer:
    """Analyze visual intensity curve for patterns."""

    def analyze(
        self,
        directives: list[SlideCompositionDirective],
    ) -> VisualIntensityCurve:
        """Analyze visual intensity distribution."""
        scores = [intensity_to_score(d.visual_intensity) for d in directives]

        if len(scores) < 2:
            return VisualIntensityCurve(
                scores=scores,
                smoothness=1.0,
                variance=0.0,
                monotonic_spans=[],
                peaks=[],
                valleys=[],
            )

        # Calculate smoothness (inverse of total variation)
        gradient = np.diff(scores)
        total_variation = np.sum(np.abs(gradient))
        smoothness = 1.0 / (1.0 + total_variation)

        # Calculate variance
        variance = float(np.var(scores))

        # Find monotonic spans (flat regions)
        monotonic_spans = []
        start = 0
        for i in range(1, len(scores)):
            if abs(scores[i] - scores[i - 1]) > 0.15:  # Threshold for "different"
                if i - start >= 3:  # At least 3 pages
                    monotonic_spans.append((start, i))
                start = i
        if len(scores) - start >= 3:
            monotonic_spans.append((start, len(scores)))

        # Find peaks and valleys
        peaks = []
        valleys = []
        for i in range(1, len(scores) - 1):
            if scores[i] > scores[i - 1] and scores[i] > scores[i + 1]:
                peaks.append(i)
            elif scores[i] < scores[i - 1] and scores[i] < scores[i + 1]:
                valleys.append(i)

        return VisualIntensityCurve(
            scores=scores,
            smoothness=smoothness,
            variance=variance,
            monotonic_spans=monotonic_spans,
            peaks=peaks,
            valleys=valleys,
        )


class PatternRecognizer:
    """Recognize problematic patterns in deck composition."""

    def recognize(
        self,
        directives: list[SlideCompositionDirective],
        intensity_curve: VisualIntensityCurve,
        qa_context: DeckQAContext,
    ) -> list[RecognizedPattern]:
        """Identify patterns that need correction."""
        patterns = []

        # Pattern 1: Monotonic regions
        for start, end in intensity_curve.monotonic_spans:
            if end - start >= 5:
                patterns.append(
                    RecognizedPattern(
                        pattern_type="monotonous_rhythm",
                        severity="moderate",
                        affected_indices=list(range(start, end)),
                        description=f"第 {start+1}-{end+1} 页视觉节奏单调",
                        suggested_fix="insert_contrast",
                    )
                )

        # Pattern 2: Excessive family repetition
        family_streak = 0
        current_family = None
        for i, directive in enumerate(directives):
            fam = directive.preferred_layout_families[0]
            if fam == current_family:
                family_streak += 1
            else:
                current_family = fam
                family_streak = 1

            if family_streak >= 4:
                patterns.append(
                    RecognizedPattern(
                        pattern_type="excessive_repetition",
                        severity="moderate",
                        affected_indices=list(range(i - 3, i + 1)),
                        description=f"连续 {family_streak} 页使用 {fam.value}",
                        suggested_fix="vary_family",
                    )
                )

        # Pattern 3: Low variance (all pages similar)
        if intensity_curve.variance < 0.05:
            patterns.append(
                RecognizedPattern(
                    pattern_type="low_variance",
                    severity="moderate",
                    affected_indices=list(range(len(directives))),
                    description="整体视觉强度变化过小",
                    suggested_fix="increase_variance",
                )
            )

        # Pattern 4: Critical QA issues
        if qa_context.critical_issues:
            patterns.append(
                RecognizedPattern(
                    pattern_type="qa_critical",
                    severity="severe",
                    affected_indices=qa_context.affected_slide_indices,
                    description="; ".join(qa_context.critical_issues[:3]),
                    suggested_fix="fix_consistency",
                    confidence=1.0,
                )
            )

        return patterns


class EnhancedDeckCompositionService(DeckCompositionPlanningService):
    """Enhanced deck composition planning with multi-dimensional analysis."""

    def __init__(self, llm_provider=None):
        super().__init__()
        self._llm = llm_provider
        self._feedback_parser = FeedbackSemanticParser(llm_provider)

    def revise_enhanced(
        self,
        plan: DeckCompositionPlan,
        feedback: str,
        *,
        slides: list[SlideSpec],
        visual_intents: list[VisualIntent],
        art_direction: ArtDirection | None = None,
        deck_qa_report: DeckQAReport | None = None,
        layout_plans: list[LayoutPlan] | None = None,
    ) -> DeckCompositionPlan:
        """Enhanced revision with multi-dimensional analysis."""

        # === Analysis Phase ===

        # 1. Parse feedback semantically
        feedback_intent = self._feedback_parser.parse(feedback)

        # 2. Analyze DeckQA context
        qa_context = DeckQAAnalyzer().analyze(deck_qa_report)

        # 3. Analyze visual intensity curve
        intensity_curve = VisualIntensityAnalyzer().analyze(plan.slide_directives)

        # 4. Recognize patterns
        patterns = PatternRecognizer().recognize(
            plan.slide_directives, intensity_curve, qa_context
        )

        # === Decision Phase ===

        # Generate new plan with base service
        revised = self.plan(
            presentation_id=plan.presentation_id,
            art_direction_id=plan.art_direction_id,
            slides=slides,
            visual_intents=visual_intents,
            art_direction=art_direction,
            auto_approve=False,
        )

        # Apply targeted adjustments based on analysis
        self._apply_targeted_adjustments(
            revised, feedback_intent, patterns, intensity_curve, qa_context
        )

        # Update metadata
        revised.id = plan.id
        revised.version = plan.version + 1
        revised.composition_strategy = (
            f"{plan.composition_strategy}（智能修订：{feedback.strip()}）"
        )
        revised.approval_status = plan.approval_status
        revised.touch()

        return revised

    def _apply_targeted_adjustments(
        self,
        plan: DeckCompositionPlan,
        feedback_intent: FeedbackIntent,
        patterns: list[RecognizedPattern],
        intensity_curve: VisualIntensityCurve,
        qa_context: DeckQAContext,
    ) -> None:
        """Apply intelligent, targeted adjustments."""

        directives = plan.slide_directives

        # Priority 1: Fix critical QA issues
        if qa_context.critical_issues:
            for idx in qa_context.affected_slide_indices:
                if 0 <= idx < len(directives):
                    # Force consistency adjustments
                    directives[idx].should_match_previous = True

        # Priority 2: Handle specific feedback
        if feedback_intent.problem_type == "monotonous_rhythm":
            self._fix_monotonous_rhythm(
                directives, intensity_curve, feedback_intent.adjustment_magnitude
            )

        elif feedback_intent.problem_type == "weak_hero":
            self._enhance_hero_slides(
                directives, feedback_intent.adjustment_magnitude, feedback_intent.specific_pages
            )

        elif feedback_intent.problem_type == "excessive_text":
            self._reduce_text_density(
                directives, feedback_intent.adjustment_magnitude, feedback_intent.specific_pages
            )

        # Priority 3: Fix recognized patterns
        for pattern in patterns:
            if pattern.severity == "severe":
                self._fix_pattern(directives, pattern)

        # Recalculate curves
        plan.visual_intensity_curve = [
            intensity_to_score(d.visual_intensity) for d in directives
        ]
        plan.density_curve = [density_to_score(d.target_density) for d in directives]

    def _fix_monotonous_rhythm(
        self,
        directives: list[SlideCompositionDirective],
        intensity_curve: VisualIntensityCurve,
        magnitude: float,
    ) -> None:
        """Fix monotonous regions by adding contrast."""
        for start, end in intensity_curve.monotonic_spans:
            # Insert contrast in the middle of monotonic spans
            mid = (start + end) // 2
            if mid < len(directives):
                directive = directives[mid]
                directive.should_contrast_previous = True

                # Boost visual intensity
                if directive.visual_intensity == VisualIntensity.LOW:
                    directive.visual_intensity = VisualIntensity.MEDIUM
                elif directive.visual_intensity == VisualIntensity.MEDIUM:
                    directive.visual_intensity = VisualIntensity.HIGH

                # Adjust priorities
                directive.hero_priority = min(1.0, directive.hero_priority + magnitude * 0.3)
                directive.text_priority = max(0.2, directive.text_priority - magnitude * 0.2)

    def _enhance_hero_slides(
        self,
        directives: list[SlideCompositionDirective],
        magnitude: float,
        specific_pages: list[int] | None,
    ) -> None:
        """Enhance hero visual prominence."""
        targets = specific_pages if specific_pages else range(len(directives))

        for idx in targets:
            if 0 <= idx < len(directives):
                directive = directives[idx]

                # Only enhance if already has some hero priority
                if directive.hero_priority >= 0.4:
                    directive.hero_priority = min(1.0, directive.hero_priority + magnitude * 0.2)
                    directive.visual_intensity = VisualIntensity.HERO
                    directive.drawing_priority = max(
                        0.2, directive.drawing_priority - magnitude * 0.1
                    )

    def _reduce_text_density(
        self,
        directives: list[SlideCompositionDirective],
        magnitude: float,
        specific_pages: list[int] | None,
    ) -> None:
        """Reduce text density and increase whitespace."""
        targets = specific_pages if specific_pages else range(len(directives))

        for idx in targets:
            if 0 <= idx < len(directives):
                directive = directives[idx]

                if directive.text_priority >= 0.6:
                    directive.text_priority = max(0.3, directive.text_priority - magnitude * 0.2)
                    directive.target_density = DensityLevel.SPACIOUS
                    directive.hero_priority = min(1.0, directive.hero_priority + magnitude * 0.15)

    def _fix_pattern(
        self,
        directives: list[SlideCompositionDirective],
        pattern: RecognizedPattern,
    ) -> None:
        """Fix a recognized pattern."""
        if pattern.suggested_fix == "vary_family":
            # Force variety in affected slides
            for idx in pattern.affected_indices[2:]:  # Keep first 2, vary rest
                if idx < len(directives):
                    directive = directives[idx]
                    directive.should_contrast_previous = True

        elif pattern.suggested_fix == "insert_contrast":
            # Add contrast in monotonic regions
            mid = pattern.affected_indices[len(pattern.affected_indices) // 2]
            if mid < len(directives):
                directives[mid].should_contrast_previous = True
                directives[mid].visual_intensity = VisualIntensity.HIGH

        elif pattern.suggested_fix == "fix_consistency":
            # Ensure consistency for affected slides
            for idx in pattern.affected_indices:
                if idx < len(directives):
                    directives[idx].should_match_previous = True
