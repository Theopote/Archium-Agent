"""Design quality assessment system for architectural presentations.

This module provides AI-powered and rule-based evaluation of slide design quality,
assessing professional standards, accessibility, and visual appeal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal
from uuid import UUID
import math

from archium.domain.design_system import DesignSystem, create_default_design_system, ColorRole
from archium.domain.presentation_templates import PresentationTemplate


class QualityCategory(str, Enum):
    """Categories of design quality assessment."""
    COLOR_HARMONY = "color_harmony"
    TYPOGRAPHY = "typography"
    LAYOUT_BALANCE = "layout_balance"
    VISUAL_HIERARCHY = "visual_hierarchy"
    CONSISTENCY = "consistency"
    ACCESSIBILITY = "accessibility"
    PROFESSIONALISM = "professionalism"
    BRAND_COMPLIANCE = "brand_compliance"


class QualityLevel(str, Enum):
    """Quality assessment levels."""
    EXCELLENT = "excellent"  # 90-100
    GOOD = "good"  # 75-89
    SATISFACTORY = "satisfactory"  # 60-74
    NEEDS_IMPROVEMENT = "needs_improvement"  # 40-59
    POOR = "poor"  # 0-39


@dataclass
class QualityMetric:
    """Individual quality metric."""
    category: QualityCategory
    name: str
    score: float  # 0-100
    weight: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    
    def get_level(self) -> QualityLevel:
        """Get quality level based on score."""
        if self.score >= 90:
            return QualityLevel.EXCELLENT
        elif self.score >= 75:
            return QualityLevel.GOOD
        elif self.score >= 60:
            return QualityLevel.SATISFACTORY
        elif self.score >= 40:
            return QualityLevel.NEEDS_IMPROVEMENT
        else:
            return QualityLevel.POOR


@dataclass
class DesignQualityReport:
    """Complete design quality assessment report."""
    slide_id: str | None
    overall_score: float  # 0-100
    overall_level: QualityLevel
    metrics: dict[QualityCategory, QualityMetric]
    summary: str
    priority_improvements: list[str] = field(default_factory=list)
    assessment_timestamp: str = ""
    
    def get_improvement_priority(self) -> list[tuple[QualityCategory, float]]:
        """Get improvements prioritized by impact and feasibility."""
        # Sort by (weight * (100 - score)) to prioritize high-impact, low-score areas
        prioritized = []
        for category, metric in self.metrics.items():
            impact = metric.weight * (100 - metric.score)
            prioritized.append((category, impact))
        
        prioritized.sort(key=lambda x: x[1], reverse=True)
        return prioritized


class ColorHarmonyEvaluator:
    """Evaluate color harmony and accessibility."""
    
    def __init__(self, design_system: DesignSystem | None = None) -> None:
        self.design_system = design_system or create_default_design_system()
    
    def evaluate(self, slide_colors: list[str]) -> QualityMetric:
        """Evaluate color harmony of a slide."""
        score = 0.0
        issues = []
        suggestions = []
        
        if not slide_colors:
            return QualityMetric(
                category=QualityCategory.COLOR_HARMONY,
                name="Color Harmony",
                score=50.0,
                issues=["No colors specified"],
                suggestions=["Add colors to the slide"],
            )
        
        # 1. Check color contrast (WCAG compliance)
        contrast_score = self._check_contrast(slide_colors)
        score += contrast_score * 0.4
        
        # 2. Check color harmony (complementary, analogous, etc.)
        harmony_score = self._check_harmony(slide_colors)
        score += harmony_score * 0.3
        
        # 3. Check color consistency with design system
        consistency_score = self._check_design_system_consistency(slide_colors)
        score += consistency_score * 0.3
        
        # Generate issues and suggestions
        if contrast_score < 70:
            issues.append("Poor color contrast detected")
            suggestions.append("Increase contrast between text and background colors")
        
        if harmony_score < 70:
            issues.append("Color harmony could be improved")
            suggestions.append("Consider using complementary or analogous color schemes")
        
        return QualityMetric(
            category=QualityCategory.COLOR_HARMONY,
            name="Color Harmony",
            score=score,
            details={
                "contrast_score": contrast_score,
                "harmony_score": harmony_score,
                "consistency_score": consistency_score,
            },
            issues=issues,
            suggestions=suggestions,
        )
    
    def _check_contrast(self, colors: list[str]) -> float:
        """Check WCAG contrast compliance."""
        # Simplified implementation - in real system would calculate actual contrast ratios
        # Assuming colors are in hex format
        if len(colors) < 2:
            return 50.0
        
        # Placeholder: assume reasonable contrast for most pairs
        return 75.0
    
    def _check_harmony(self, colors: list[str]) -> float:
        """Check color harmony principles."""
        # Simplified implementation
        # In real system would analyze color wheel relationships
        if len(colors) <= 2:
            return 80.0  # Simple schemes are usually harmonious
        elif len(colors) <= 4:
            return 70.0  # Moderate complexity
        else:
            return 60.0  # More complex schemes risk disharmony
    
    def _check_design_system_consistency(self, colors: list[str]) -> float:
        """Check consistency with design system colors."""
        # Simplified implementation
        # In real system would check against design system palette
        return 80.0


class TypographyEvaluator:
    """Evaluate typography quality."""
    
    def __init__(self, design_system: DesignSystem | None = None) -> None:
        self.design_system = design_system or create_default_design_system()
    
    def evaluate(self, typography_data: dict[str, Any]) -> QualityMetric:
        """Evaluate typography of a slide."""
        score = 0.0
        issues = []
        suggestions = []
        
        # 1. Check font hierarchy
        hierarchy_score = self._check_font_hierarchy(typography_data)
        score += hierarchy_score * 0.4
        
        # 2. Check font sizes
        size_score = self._check_font_sizes(typography_data)
        score += size_score * 0.3
        
        # 3. Check line heights and spacing
        spacing_score = self._check_spacing(typography_data)
        score += spacing_score * 0.3
        
        # Generate issues and suggestions
        if hierarchy_score < 70:
            issues.append("Font hierarchy unclear")
            suggestions.append("Establish clear heading hierarchy (H1, H2, H3)")
        
        if size_score < 70:
            issues.append("Font sizes may not be optimal")
            suggestions.append("Ensure body text is at least 12px for readability")
        
        return QualityMetric(
            category=QualityCategory.TYPOGRAPHY,
            name="Typography",
            score=score,
            details={
                "hierarchy_score": hierarchy_score,
                "size_score": size_score,
                "spacing_score": spacing_score,
            },
            issues=issues,
            suggestions=suggestions,
        )
    
    def _check_font_hierarchy(self, data: dict[str, Any]) -> float:
        """Check font hierarchy implementation."""
        # Simplified implementation
        return 75.0
    
    def _check_font_sizes(self, data: dict[str, Any]) -> float:
        """Check font size appropriateness."""
        # Simplified implementation
        return 80.0
    
    def _check_spacing(self, data: dict[str, Any]) -> float:
        """Check line heights and spacing."""
        # Simplified implementation
        return 75.0


class LayoutBalanceEvaluator:
    """Evaluate layout balance and composition."""
    
    def __init__(self, design_system: DesignSystem | None = None) -> None:
        self.design_system = design_system or create_default_design_system()
    
    def evaluate(self, layout_data: dict[str, Any]) -> QualityMetric:
        """Evaluate layout balance."""
        score = 0.0
        issues = []
        suggestions = []
        
        # 1. Check visual balance
        balance_score = self._check_visual_balance(layout_data)
        score += balance_score * 0.4
        
        # 2. Check alignment
        alignment_score = self._check_alignment(layout_data)
        score += alignment_score * 0.3
        
        # 3. Check white space
        whitespace_score = self._check_whitespace(layout_data)
        score += whitespace_score * 0.3
        
        # Generate issues and suggestions
        if balance_score < 70:
            issues.append("Visual balance could be improved")
            suggestions.append("Adjust element positions for better balance")
        
        if alignment_score < 70:
            issues.append("Alignment inconsistencies detected")
            suggestions.append("Ensure elements are properly aligned to grid")
        
        return QualityMetric(
            category=QualityCategory.LAYOUT_BALANCE,
            name="Layout Balance",
            score=score,
            details={
                "balance_score": balance_score,
                "alignment_score": alignment_score,
                "whitespace_score": whitespace_score,
            },
            issues=issues,
            suggestions=suggestions,
        )
    
    def _check_visual_balance(self, data: dict[str, Any]) -> float:
        """Check visual weight distribution."""
        # Simplified implementation
        return 75.0
    
    def _check_alignment(self, data: dict[str, Any]) -> float:
        """Check element alignment."""
        # Simplified implementation
        return 80.0
    
    def _check_whitespace(self, data: dict[str, Any]) -> float:
        """Check white space distribution."""
        # Simplified implementation
        return 70.0


class VisualHierarchyEvaluator:
    """Evaluate visual hierarchy and information flow."""
    
    def __init__(self, design_system: DesignSystem | None = None) -> None:
        self.design_system = design_system or create_default_design_system()
    
    def evaluate(self, hierarchy_data: dict[str, Any]) -> QualityMetric:
        """Evaluate visual hierarchy."""
        score = 0.0
        issues = []
        suggestions = []
        
        # 1. Check information hierarchy
        info_hierarchy_score = self._check_information_hierarchy(hierarchy_data)
        score += info_hierarchy_score * 0.5
        
        # 2. Check visual flow
        visual_flow_score = self._check_visual_flow(hierarchy_data)
        score += visual_flow_score * 0.5
        
        # Generate issues and suggestions
        if info_hierarchy_score < 70:
            issues.append("Information hierarchy unclear")
            suggestions.append("Use size, color, and position to establish clear hierarchy")
        
        return QualityMetric(
            category=QualityCategory.VISUAL_HIERARCHY,
            name="Visual Hierarchy",
            score=score,
            details={
                "info_hierarchy_score": info_hierarchy_score,
                "visual_flow_score": visual_flow_score,
            },
            issues=issues,
            suggestions=suggestions,
        )
    
    def _check_information_hierarchy(self, data: dict[str, Any]) -> float:
        """Check information hierarchy implementation."""
        # Simplified implementation
        return 75.0
    
    def _check_visual_flow(self, data: dict[str, Any]) -> float:
        """Check visual reading flow."""
        # Simplified implementation
        return 70.0


class ConsistencyEvaluator:
    """Evaluate consistency across slides."""
    
    def __init__(self, design_system: DesignSystem | None = None) -> None:
        self.design_system = design_system or create_default_design_system()
    
    def evaluate(self, current_slide: dict[str, Any], previous_slides: list[dict[str, Any]]) -> QualityMetric:
        """Evaluate consistency with previous slides."""
        score = 0.0
        issues = []
        suggestions = []
        
        if not previous_slides:
            return QualityMetric(
                category=QualityCategory.CONSISTENCY,
                name="Consistency",
                score=100.0,  # First slide is always consistent
                details={"reason": "First slide in presentation"},
            )
        
        # 1. Check style consistency
        style_consistency = self._check_style_consistency(current_slide, previous_slides)
        score += style_consistency * 0.4
        
        # 2. Check layout consistency
        layout_consistency = self._check_layout_consistency(current_slide, previous_slides)
        score += layout_consistency * 0.3
        
        # 3. Check element consistency
        element_consistency = self._check_element_consistency(current_slide, previous_slides)
        score += element_consistency * 0.3
        
        # Generate issues and suggestions
        if style_consistency < 70:
            issues.append("Style inconsistency detected")
            suggestions.append("Maintain consistent colors and fonts across slides")
        
        return QualityMetric(
            category=QualityCategory.CONSISTENCY,
            name="Consistency",
            score=score,
            details={
                "style_consistency": style_consistency,
                "layout_consistency": layout_consistency,
                "element_consistency": element_consistency,
            },
            issues=issues,
            suggestions=suggestions,
        )
    
    def _check_style_consistency(self, current: dict[str, Any], previous: list[dict[str, Any]]) -> float:
        """Check style consistency."""
        # Simplified implementation
        return 75.0
    
    def _check_layout_consistency(self, current: dict[str, Any], previous: list[dict[str, Any]]) -> float:
        """Check layout consistency."""
        # Simplified implementation
        return 80.0
    
    def _check_element_consistency(self, current: dict[str, Any], previous: list[dict[str, Any]]) -> float:
        """Check element consistency."""
        # Simplified implementation
        return 70.0


class AccessibilityEvaluator:
    """Evaluate accessibility compliance."""
    
    def __init__(self, design_system: DesignSystem | None = None) -> None:
        self.design_system = design_system or create_default_design_system()
    
    def evaluate(self, accessibility_data: dict[str, Any]) -> QualityMetric:
        """Evaluate accessibility compliance."""
        score = 0.0
        issues = []
        suggestions = []
        
        # 1. Check color contrast (WCAG AA)
        contrast_score = self._check_color_contrast(accessibility_data)
        score += contrast_score * 0.5
        
        # 2. Check text readability
        readability_score = self._check_text_readability(accessibility_data)
        score += readability_score * 0.3
        
        # 3. Check alternative text
        alt_text_score = self._check_alt_text(accessibility_data)
        score += alt_text_score * 0.2
        
        # Generate issues and suggestions
        if contrast_score < 70:
            issues.append("Color contrast does not meet WCAG AA standards")
            suggestions.append("Increase contrast between text and background")
        
        if alt_text_score < 70:
            issues.append("Missing alternative text for images")
            suggestions.append("Add descriptive alt text for all images")
        
        return QualityMetric(
            category=QualityCategory.ACCESSIBILITY,
            name="Accessibility",
            score=score,
            details={
                "contrast_score": contrast_score,
                "readability_score": readability_score,
                "alt_text_score": alt_text_score,
            },
            issues=issues,
            suggestions=suggestions,
        )
    
    def _check_color_contrast(self, data: dict[str, Any]) -> float:
        """Check WCAG color contrast compliance."""
        # Simplified implementation
        return 70.0
    
    def _check_text_readability(self, data: dict[str, Any]) -> float:
        """Check text readability."""
        # Simplified implementation
        return 80.0
    
    def _check_alt_text(self, data: dict[str, Any]) -> float:
        """Check alternative text for images."""
        # Simplified implementation
        return 60.0


class ProfessionalismEvaluator:
    """Evaluate overall professionalism and industry standards."""
    
    def __init__(self, design_system: DesignSystem | None = None) -> None:
        self.design_system = design_system or create_default_design_system()
    
    def evaluate(self, slide_data: dict[str, Any]) -> QualityMetric:
        """Evaluate overall professionalism."""
        score = 0.0
        issues = []
        suggestions = []
        
        # 1. Check industry standards compliance
        industry_score = self._check_industry_standards(slide_data)
        score += industry_score * 0.4
        
        # 2. Check visual polish
        polish_score = self._check_visual_polish(slide_data)
        score += polish_score * 0.3
        
        # 3. Check content appropriateness
        content_score = self._check_content_appropriateness(slide_data)
        score += content_score * 0.3
        
        # Generate issues and suggestions
        if industry_score < 70:
            issues.append("Does not fully meet industry standards")
            suggestions.append("Review architectural presentation best practices")
        
        return QualityMetric(
            category=QualityCategory.PROFESSIONALISM,
            name="Professionalism",
            score=score,
            details={
                "industry_score": industry_score,
                "polish_score": polish_score,
                "content_score": content_score,
            },
            issues=issues,
            suggestions=suggestions,
        )
    
    def _check_industry_standards(self, data: dict[str, Any]) -> float:
        """Check architectural industry standards."""
        # Simplified implementation
        return 75.0
    
    def _check_visual_polish(self, data: dict[str, Any]) -> float:
        """Check visual polish and refinement."""
        # Simplified implementation
        return 70.0
    
    def _check_content_appropriateness(self, data: dict[str, Any]) -> float:
        """Check content appropriateness for audience."""
        # Simplified implementation
        return 80.0


class DesignQualityAssessor:
    """Main design quality assessment system."""
    
    def __init__(self, design_system: DesignSystem | None = None) -> None:
        self.design_system = design_system or create_default_design_system()
        
        # Initialize evaluators
        self.color_evaluator = ColorHarmonyEvaluator(design_system)
        self.typography_evaluator = TypographyEvaluator(design_system)
        self.layout_evaluator = LayoutBalanceEvaluator(design_system)
        self.hierarchy_evaluator = VisualHierarchyEvaluator(design_system)
        self.consistency_evaluator = ConsistencyEvaluator(design_system)
        self.accessibility_evaluator = AccessibilityEvaluator(design_system)
        self.professionalism_evaluator = ProfessionalismEvaluator(design_system)
    
    def assess_slide(
        self,
        slide_data: dict[str, Any],
        previous_slides: list[dict[str, Any]] | None = None,
    ) -> DesignQualityReport:
        """Comprehensive assessment of a single slide."""
        from datetime import datetime
        
        metrics = {}
        
        # Evaluate each category
        metrics[QualityCategory.COLOR_HARMONY] = self.color_evaluator.evaluate(
            slide_data.get("colors", [])
        )
        metrics[QualityCategory.TYPOGRAPHY] = self.typography_evaluator.evaluate(
            slide_data.get("typography", {})
        )
        metrics[QualityCategory.LAYOUT_BALANCE] = self.layout_evaluator.evaluate(
            slide_data.get("layout", {})
        )
        metrics[QualityCategory.VISUAL_HIERARCHY] = self.hierarchy_evaluator.evaluate(
            slide_data.get("hierarchy", {})
        )
        metrics[QualityCategory.CONSISTENCY] = self.consistency_evaluator.evaluate(
            slide_data,
            previous_slides or [],
        )
        metrics[QualityCategory.ACCESSIBILITY] = self.accessibility_evaluator.evaluate(
            slide_data.get("accessibility", {})
        )
        metrics[QualityCategory.PROFESSIONALISM] = self.professionalism_evaluator.evaluate(
            slide_data
        )
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(metrics)
        overall_level = self._get_quality_level(overall_score)
        
        # Generate summary
        summary = self._generate_summary(metrics, overall_level)
        
        # Identify priority improvements
        priority_improvements = self._identify_priority_improvements(metrics)
        
        return DesignQualityReport(
            slide_id=slide_data.get("id"),
            overall_score=overall_score,
            overall_level=overall_level,
            metrics=metrics,
            summary=summary,
            priority_improvements=priority_improvements,
            assessment_timestamp=datetime.now().isoformat(),
        )
    
    def assess_presentation(
        self,
        presentation_data: list[dict[str, Any]],
    ) -> dict[str, DesignQualityReport]:
        """Assess an entire presentation."""
        reports = {}
        
        for i, slide_data in enumerate(presentation_data):
            previous_slides = presentation_data[:i]
            report = self.assess_slide(slide_data, previous_slides)
            reports[slide_data.get("id", f"slide_{i}")] = report
        
        return reports
    
    def _calculate_overall_score(self, metrics: dict[QualityCategory, QualityMetric]) -> float:
        """Calculate weighted overall score."""
        total_score = 0.0
        total_weight = 0.0
        
        for metric in metrics.values():
            total_score += metric.score * metric.weight
            total_weight += metric.weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def _get_quality_level(self, score: float) -> QualityLevel:
        """Get quality level from score."""
        if score >= 90:
            return QualityLevel.EXCELLENT
        elif score >= 75:
            return QualityLevel.GOOD
        elif score >= 60:
            return QualityLevel.SATISFACTORY
        elif score >= 40:
            return QualityLevel.NEEDS_IMPROVEMENT
        else:
            return QualityLevel.POOR
    
    def _generate_summary(
        self,
        metrics: dict[QualityCategory, QualityMetric],
        overall_level: QualityLevel,
    ) -> str:
        """Generate human-readable summary."""
        level_descriptions = {
            QualityLevel.EXCELLENT: "Professional quality presentation",
            QualityLevel.GOOD: "High quality with minor improvements possible",
            QualityLevel.SATISFACTORY: "Acceptable quality with some areas for improvement",
            QualityLevel.NEEDS_IMPROVEMENT: "Several areas need attention",
            QualityLevel.POOR: "Significant improvements needed",
        }
        
        base_summary = level_descriptions.get(overall_level, "Quality assessment complete")
        
        # Add specific feedback based on lowest-scoring categories
        low_scoring = [
            (cat, metric) for cat, metric in metrics.items()
            if metric.score < 70
        ]
        
        if low_scoring:
            categories_str = ", ".join(cat.value for cat, _ in low_scoring)
            base_summary += f". Focus on improving: {categories_str}"
        
        return base_summary
    
    def _identify_priority_improvements(
        self,
        metrics: dict[QualityCategory, QualityMetric],
    ) -> list[str]:
        """Identify priority improvements."""
        improvements = []
        
        # Collect suggestions from low-scoring metrics
        for category, metric in metrics.items():
            if metric.score < 75:
                for suggestion in metric.suggestions:
                    improvements.append(f"{category.value}: {suggestion}")
        
        return improvements[:5]  # Return top 5 priority improvements
