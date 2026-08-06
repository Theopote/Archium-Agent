"""Layout planning path metrics and monitoring.

This module tracks usage of legacy (content-type) vs. new (composition-driven)
layout planning paths to inform deprecation decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LayoutPlanningPath(StrEnum):
    """Which layout planning path was used."""

    COMPOSITION_DRIVEN = "composition_driven"
    """New path: PageType + CompositionStrategy → LayoutFamily."""

    CONTENT_TYPE_LEGACY = "content_type_legacy"
    """Legacy path: VisualContentType → LayoutFamily."""

    FALLBACK = "fallback"
    """Fallback when neither path has sufficient data."""


@dataclass
class LayoutPlanningMetrics:
    """Metrics for a layout planning operation."""

    path_used: LayoutPlanningPath
    """Which path was selected."""

    has_page_type: bool
    """Whether VisualIntent had page_type set."""

    has_structured_composition: bool
    """Whether VisualIntent had structured CompositionStrategy."""

    selected_family: str
    """The LayoutFamily that was selected."""

    candidate_count: int
    """Number of candidates generated."""

    slide_id: str | None = None
    """Optional slide ID for detailed tracking."""

    presentation_id: str | None = None
    """Optional presentation ID for project-level analysis."""


class LayoutPlanningMetricsCollector:
    """Collects and aggregates layout planning metrics."""

    def __init__(self) -> None:
        self._metrics: list[LayoutPlanningMetrics] = []

    def record(self, metric: LayoutPlanningMetrics) -> None:
        """Record a single layout planning operation."""
        self._metrics.append(metric)

    def get_all(self) -> list[LayoutPlanningMetrics]:
        """Return all recorded metrics."""
        return list(self._metrics)

    def clear(self) -> None:
        """Clear all recorded metrics."""
        self._metrics.clear()

    def compute_summary(self) -> LayoutPlanningMetricsSummary:
        """Compute aggregate statistics."""
        if not self._metrics:
            return LayoutPlanningMetricsSummary(
                total_operations=0,
                composition_driven_count=0,
                content_type_legacy_count=0,
                fallback_count=0,
                composition_driven_percentage=0.0,
                has_page_type_count=0,
                has_structured_composition_count=0,
            )

        total = len(self._metrics)
        composition_count = sum(
            1 for m in self._metrics if m.path_used == LayoutPlanningPath.COMPOSITION_DRIVEN
        )
        legacy_count = sum(
            1 for m in self._metrics if m.path_used == LayoutPlanningPath.CONTENT_TYPE_LEGACY
        )
        fallback_count = sum(
            1 for m in self._metrics if m.path_used == LayoutPlanningPath.FALLBACK
        )
        page_type_count = sum(1 for m in self._metrics if m.has_page_type)
        structured_comp_count = sum(1 for m in self._metrics if m.has_structured_composition)

        return LayoutPlanningMetricsSummary(
            total_operations=total,
            composition_driven_count=composition_count,
            content_type_legacy_count=legacy_count,
            fallback_count=fallback_count,
            composition_driven_percentage=100.0 * composition_count / total if total > 0 else 0.0,
            has_page_type_count=page_type_count,
            has_structured_composition_count=structured_comp_count,
        )


@dataclass
class LayoutPlanningMetricsSummary:
    """Aggregate statistics for layout planning path usage."""

    total_operations: int
    composition_driven_count: int
    content_type_legacy_count: int
    fallback_count: int
    composition_driven_percentage: float

    has_page_type_count: int
    has_structured_composition_count: int

    def is_ready_for_deprecation(self, threshold: float = 90.0) -> bool:
        """Check if composition-driven path usage exceeds threshold for deprecation.

        Args:
            threshold: Percentage threshold (default 90.0%)

        Returns:
            True if composition_driven_percentage >= threshold
        """
        return self.composition_driven_percentage >= threshold

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/export."""
        return {
            "total_operations": self.total_operations,
            "composition_driven_count": self.composition_driven_count,
            "content_type_legacy_count": self.content_type_legacy_count,
            "fallback_count": self.fallback_count,
            "composition_driven_percentage": round(self.composition_driven_percentage, 2),
            "has_page_type_count": self.has_page_type_count,
            "has_structured_composition_count": self.has_structured_composition_count,
            "ready_for_deprecation_90pct": self.is_ready_for_deprecation(90.0),
            "ready_for_deprecation_95pct": self.is_ready_for_deprecation(95.0),
        }


# Global metrics collector (can be replaced with proper observability in production)
_GLOBAL_COLLECTOR = LayoutPlanningMetricsCollector()


def record_layout_planning_path(metric: LayoutPlanningMetrics) -> None:
    """Record a layout planning path selection (global convenience function)."""
    _GLOBAL_COLLECTOR.record(metric)


def get_layout_planning_summary() -> LayoutPlanningMetricsSummary:
    """Get aggregate metrics summary (global convenience function)."""
    return _GLOBAL_COLLECTOR.compute_summary()


def clear_layout_planning_metrics() -> None:
    """Clear all recorded metrics (global convenience function)."""
    _GLOBAL_COLLECTOR.clear()
