"""Page type classification — pure content taxonomy decoupled from visual style.

PageType identifies WHAT content is being presented, independent of HOW it's
visually expressed. This allows the same content type to be rendered with
different composition strategies and style presets.

Architectural Rationale:
    Previously, LayoutFamily conflated content type with visual style
    (e.g., "HERO" = hero content + full-bleed style). This prevented
    the same content from being expressed in different visual languages
    (BIG bold vs. SOM minimal vs. OMA collage).

    PageType → CompositionStrategy → LayoutFamily → LayoutPlan
    (content)    (design judgment)    (impl detail)   (geometry)
"""

from __future__ import annotations

from enum import StrEnum


class PageType(StrEnum):
    """Pure content classification — decoupled from composition or visual style.

    Each PageType describes the semantic role and content structure of a slide,
    not how it should look. Visual expression is determined by CompositionStrategy
    and StylePreset layered on top.

    Design principle: The same PageType can be rendered with vastly different
    visual approaches depending on the architectural office's visual language.
    """

    # Opening & Structure
    COVER = "cover"
    """Project title page or deck cover. Typically minimal content, maximum impact."""

    SECTION_OPENER = "section_opener"
    """Chapter or section divider. Establishes narrative transition."""

    # Context & Analysis
    SITE_ANALYSIS = "site_analysis"
    """Site context, constraints, opportunities. May include maps, photos, diagrams."""

    PROGRAM_ANALYSIS = "program_analysis"
    """Functional requirements, spatial needs, user analysis."""

    CONTEXTUAL_PRECEDENT = "contextual_precedent"
    """Reference projects, case studies, precedent analysis."""

    # Design Intent
    STRATEGY = "strategy"
    """Design principles, strategic approach, conceptual framework."""

    CONCEPT = "concept"
    """Design concept, parti diagram, organizing idea."""

    # Evidence & Documentation
    EVIDENCE = "evidence"
    """Supporting evidence: photos, observations, field documentation."""

    COMPARISON = "comparison"
    """Side-by-side comparison of options, scenarios, or alternatives."""

    # Process & Development
    PROCESS = "process"
    """Design process, timeline, phased development."""

    ITERATION = "iteration"
    """Design exploration, option studies, refinement progression."""

    # Technical Documentation
    TECHNICAL_DRAWING = "technical_drawing"
    """Plans, sections, elevations, details — technical precision required."""

    SPATIAL_ANALYSIS = "spatial_analysis"
    """Diagrams analyzing spatial relationships, circulation, zoning."""

    # Data & Metrics
    DATA_METRICS = "data_metrics"
    """Quantitative data: metrics, statistics, performance indicators."""

    COST_SCHEDULE = "cost_schedule"
    """Budget, timeline, resource allocation."""

    # Argumentation
    TEXT_ARGUMENT = "text_argument"
    """Text-led reasoning, policy argument, written justification."""

    RECOMMENDATION = "recommendation"
    """Conclusion, decision point, recommended action."""

    # Mixed & Flexible
    MIXED_CONTENT = "mixed_content"
    """Hybrid content that doesn't fit a single category."""


# Mapping: PageType → likely LayoutFamily candidates (for backward compatibility)
# This is a compatibility bridge during the transition period. Eventually,
# LayoutFamily should be selected by CompositionStrategy, not PageType.
PAGE_TYPE_TO_LAYOUT_FAMILY_HINTS: dict[PageType, list[str]] = {
    PageType.COVER: ["hero", "textual_argument"],
    PageType.SECTION_OPENER: ["hero", "textual_argument"],
    PageType.SITE_ANALYSIS: ["evidence_board", "drawing_focus", "hybrid_canvas"],
    PageType.PROGRAM_ANALYSIS: ["textual_argument", "metric_dashboard", "strategy_cards"],
    PageType.CONTEXTUAL_PRECEDENT: ["evidence_board", "comparative_matrix"],
    PageType.STRATEGY: ["strategy_cards", "textual_argument", "hero"],
    PageType.CONCEPT: ["hero", "analytical_diagram", "hybrid_canvas"],
    PageType.EVIDENCE: ["evidence_board", "comparative_matrix"],
    PageType.COMPARISON: ["comparative_matrix", "evidence_board"],
    PageType.PROCESS: ["process_narrative", "analytical_diagram"],
    PageType.ITERATION: ["comparative_matrix", "evidence_board"],
    PageType.TECHNICAL_DRAWING: ["drawing_focus", "analytical_diagram"],
    PageType.SPATIAL_ANALYSIS: ["analytical_diagram", "drawing_focus"],
    PageType.DATA_METRICS: ["metric_dashboard", "analytical_diagram"],
    PageType.COST_SCHEDULE: ["metric_dashboard", "textual_argument"],
    PageType.TEXT_ARGUMENT: ["textual_argument", "strategy_cards"],
    PageType.RECOMMENDATION: ["strategy_cards", "textual_argument", "hero"],
    PageType.MIXED_CONTENT: ["hybrid_canvas", "evidence_board"],
}


def infer_page_type_from_layout_family(family: str) -> PageType:
    """Reverse mapping: LayoutFamily → likely PageType (heuristic fallback).

    Used for backward compatibility when VisualIntent has preferred_layout_families
    but no page_type set.
    """
    family_lower = family.lower()

    if family_lower == "hero":
        return PageType.COVER
    if family_lower == "evidence_board":
        return PageType.EVIDENCE
    if family_lower == "drawing_focus":
        return PageType.TECHNICAL_DRAWING
    if family_lower == "comparative_matrix":
        return PageType.COMPARISON
    if family_lower == "process_narrative":
        return PageType.PROCESS
    if family_lower == "analytical_diagram":
        return PageType.SPATIAL_ANALYSIS
    if family_lower == "metric_dashboard":
        return PageType.DATA_METRICS
    if family_lower == "strategy_cards":
        return PageType.STRATEGY
    if family_lower == "textual_argument":
        return PageType.TEXT_ARGUMENT
    if family_lower == "hybrid_canvas":
        return PageType.MIXED_CONTENT

    # Default fallback
    return PageType.MIXED_CONTENT


def suggest_page_type_from_content(
    *,
    has_site_map: bool = False,
    has_technical_drawing: bool = False,
    has_data_chart: bool = False,
    has_comparison_structure: bool = False,
    has_timeline: bool = False,
    text_is_argumentative: bool = False,
    is_opening_slide: bool = False,
) -> PageType:
    """Heuristic content analysis → PageType suggestion.

    Use this when SlideSpec content needs to be classified but no explicit
    page_type was provided.
    """
    if is_opening_slide:
        return PageType.COVER

    if has_site_map:
        return PageType.SITE_ANALYSIS

    if has_technical_drawing:
        return PageType.TECHNICAL_DRAWING

    if has_data_chart:
        return PageType.DATA_METRICS

    if has_comparison_structure:
        return PageType.COMPARISON

    if has_timeline:
        return PageType.PROCESS

    if text_is_argumentative:
        return PageType.TEXT_ARGUMENT

    # Default fallback
    return PageType.MIXED_CONTENT
