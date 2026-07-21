"""Semantic block types for specialized scene compilation.

Distinct from layout geometry (``LayoutFamily``) and free-composition
``VisualContentType``. Driven by ``ArchitecturalContentSchema``,
``VisualIntent``, and layout family — never by JSON shape heuristics.
"""

from __future__ import annotations

from enum import StrEnum

from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema
from archium.domain.visual.enums import LayoutFamily, VisualContentType
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.template_induction import ArchitecturalContentType
from archium.domain.visual.visual_intent import VisualIntent


class SemanticBlockType(StrEnum):
    """Page-level communication pattern selecting a SceneCompiler."""

    DRAWING_FOCUS = "drawing_focus"
    PHOTO_EVIDENCE_GRID = "photo_evidence_grid"
    BEFORE_AFTER = "before_after"
    METRIC = "metric"
    DECISION = "decision"
    GENERIC = "generic"


_SCHEMA_TO_BLOCK: dict[ArchitecturalContentType, SemanticBlockType] = {
    ArchitecturalContentType.DRAWING_FOCUS: SemanticBlockType.DRAWING_FOCUS,
    ArchitecturalContentType.DIAGRAM: SemanticBlockType.DRAWING_FOCUS,
    ArchitecturalContentType.PHOTO_ANALYSIS: SemanticBlockType.PHOTO_EVIDENCE_GRID,
    ArchitecturalContentType.MULTI_IMAGE_GRID: SemanticBlockType.PHOTO_EVIDENCE_GRID,
    ArchitecturalContentType.IMAGE_TEXT_HYBRID: SemanticBlockType.PHOTO_EVIDENCE_GRID,
    ArchitecturalContentType.BEFORE_AFTER: SemanticBlockType.BEFORE_AFTER,
    ArchitecturalContentType.CASE_COMPARISON: SemanticBlockType.BEFORE_AFTER,
    ArchitecturalContentType.METRIC_SUMMARY: SemanticBlockType.METRIC,
    ArchitecturalContentType.CONCLUSION: SemanticBlockType.DECISION,
}

_VISUAL_CONTENT_TO_BLOCK: dict[VisualContentType, SemanticBlockType] = {
    VisualContentType.SITE_PLAN: SemanticBlockType.DRAWING_FOCUS,
    VisualContentType.FLOOR_PLAN: SemanticBlockType.DRAWING_FOCUS,
    VisualContentType.SECTION: SemanticBlockType.DRAWING_FOCUS,
    VisualContentType.ELEVATION: SemanticBlockType.DRAWING_FOCUS,
    VisualContentType.ANALYTICAL_DIAGRAM: SemanticBlockType.DRAWING_FOCUS,
    VisualContentType.PHOTO_EVIDENCE: SemanticBlockType.PHOTO_EVIDENCE_GRID,
    VisualContentType.COMPARISON: SemanticBlockType.BEFORE_AFTER,
    VisualContentType.METRICS: SemanticBlockType.METRIC,
}

_LAYOUT_FAMILY_TO_BLOCK: dict[LayoutFamily, SemanticBlockType] = {
    LayoutFamily.DRAWING_FOCUS: SemanticBlockType.DRAWING_FOCUS,
    LayoutFamily.ANALYTICAL_DIAGRAM: SemanticBlockType.DRAWING_FOCUS,
    LayoutFamily.EVIDENCE_BOARD: SemanticBlockType.PHOTO_EVIDENCE_GRID,
    LayoutFamily.COMPARATIVE_MATRIX: SemanticBlockType.BEFORE_AFTER,
    LayoutFamily.METRIC_DASHBOARD: SemanticBlockType.METRIC,
}


def resolve_semantic_block_type(
    *,
    schema: ArchitecturalContentSchema | None = None,
    visual_intent: VisualIntent | None = None,
    layout_plan: LayoutPlan | None = None,
) -> SemanticBlockType:
    """Resolve block type from explicit semantic signals (schema → intent → family)."""
    if schema is not None:
        mapped = _SCHEMA_TO_BLOCK.get(schema.content_type)
        if mapped is not None:
            return mapped
        if any(req.role.value == "decision_request" for req in schema.required_content):
            return SemanticBlockType.DECISION

    if visual_intent is not None:
        mapped = _VISUAL_CONTENT_TO_BLOCK.get(visual_intent.dominant_content_type)
        if mapped is not None:
            return mapped
        if visual_intent.continuity_role.value in {"summary", "closing"}:
            return SemanticBlockType.DECISION

    if layout_plan is not None:
        mapped = _LAYOUT_FAMILY_TO_BLOCK.get(layout_plan.layout_family)
        if mapped is not None:
            return mapped

    return SemanticBlockType.GENERIC
