"""Project context intelligence domain types."""

from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.legacy_origin import (
    apply_legacy_origin,
    infer_legacy_origin_mode,
)
from archium.domain.context.project_context import (
    ProjectContext,
    infer_lifecycle_stage,
    infer_recommended_workflow,
    primary_page_for_workflow,
)
from archium.domain.context.recommended_workflow import RecommendedWorkflow

__all__ = [
    "ProjectContext",
    "ProjectLifecycleStage",
    "RecommendedWorkflow",
    "apply_legacy_origin",
    "infer_legacy_origin_mode",
    "infer_lifecycle_stage",
    "infer_recommended_workflow",
    "primary_page_for_workflow",
]
