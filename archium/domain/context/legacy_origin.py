"""Map ProjectContext to legacy ProjectOriginMode (compat field only)."""

from __future__ import annotations

from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.enums import ProjectOriginMode


def infer_legacy_origin_mode(ctx: ProjectContext) -> ProjectOriginMode:
    """Derive compat origin_mode from knowledge + workflow (not user-selected mode)."""
    ks = ctx.knowledge_state
    workflow = ctx.recommended_workflow

    if workflow == RecommendedWorkflow.DELIVER:
        return ProjectOriginMode.EXISTING_PROJECT
    if workflow == RecommendedWorkflow.MATERIALS and ks.completeness_score >= 0.55:
        return ProjectOriginMode.EXISTING_PROJECT

    if ctx.suggested_origin_mode == ProjectOriginMode.RESEARCH_PROGRAMMING:
        if workflow in (RecommendedWorkflow.RESEARCH, RecommendedWorkflow.MISSION):
            return ProjectOriginMode.RESEARCH_PROGRAMMING
        if ctx.lifecycle_stage == ProjectLifecycleStage.RESEARCH and ks.completeness_score < 0.5:
            return ProjectOriginMode.RESEARCH_PROGRAMMING

    if workflow == RecommendedWorkflow.RESEARCH and ks.completeness_score < 0.42:
        return ProjectOriginMode.RESEARCH_PROGRAMMING

    return ProjectOriginMode.CONCEPT_EXPLORATION


def apply_legacy_origin(ctx: ProjectContext) -> ProjectContext:
    """Return context copy with suggested_origin_mode aligned to routing policy."""
    legacy = infer_legacy_origin_mode(ctx)
    if ctx.suggested_origin_mode == legacy:
        return ctx
    return ctx.model_copy(update={"suggested_origin_mode": legacy})
