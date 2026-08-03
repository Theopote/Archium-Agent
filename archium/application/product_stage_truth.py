"""Single product-stage truth (Topic 07 / WF-010).

OrchestrationPlan and presentation heuristics both imply progress. Main chrome
must show one of the five product stages (materials → … → deliver).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.domain.orchestration.models import (
    OrchestrationPlan,
    OrchestrationStage,
    OrchestrationStageStatus,
)

PRIMARY_STAGE_IDS = frozenset(
    {"materials", "outline", "generate", "edit", "deliver"}
)

# Map orchestration stages onto the five-stage product chrome.
_ORCH_TO_PRODUCT: dict[OrchestrationStage, str] = {
    OrchestrationStage.EXPLORE: "outline",
    OrchestrationStage.RESEARCH: "outline",
    OrchestrationStage.MATERIALS: "materials",
    OrchestrationStage.MISSION_PLANNING: "outline",
    OrchestrationStage.WORKSTREAM_EXECUTION: "outline",
    OrchestrationStage.PRESENTATION: "generate",
    OrchestrationStage.VISUAL: "edit",
    OrchestrationStage.DELIVER: "deliver",
}

_DONE = frozenset(
    {
        OrchestrationStageStatus.COMPLETED,
        OrchestrationStageStatus.SKIPPED,
        OrchestrationStageStatus.FAILED,
    }
)


@dataclass(frozen=True)
class ProductStageTruth:
    """One authoritative product-flow stage for chrome / continue hints."""

    stage_id: str
    source: str  # orchestration | presentation
    orchestration_stage: str | None = None

    @property
    def label(self) -> str:
        labels = {
            "materials": "资料",
            "outline": "大纲",
            "generate": "生成",
            "edit": "工作室",
            "deliver": "交付",
        }
        return labels.get(self.stage_id, "资料")


def product_stage_id_for_orchestration(stage: OrchestrationStage) -> str:
    """Map an orchestration stage onto a primary product-flow stage id."""
    return _ORCH_TO_PRODUCT.get(stage, "outline")


def active_orchestration_product_stage(
    session: SessionLike,
    project_id: UUID,
) -> ProductStageTruth | None:
    """If an orchestration run is active, return its mapped product stage."""
    session = session_of(session)
    from archium.domain.enums import WorkflowStatus
    from archium.infrastructure.database.repositories import WorkflowRunRepository

    for run in WorkflowRunRepository(session).list_by_project(project_id):
        if run.state.get("workflow_kind") != "orchestration":
            continue
        if run.status not in {WorkflowStatus.RUNNING, WorkflowStatus.AWAITING_REVIEW}:
            continue
        raw = run.state.get("orchestration_plan")
        if not isinstance(raw, dict):
            continue
        try:
            plan = OrchestrationPlan.model_validate(raw)
        except Exception:
            continue
        stage = plan.active_stage()
        if stage is None or stage.status in _DONE:
            continue
        stage_id = product_stage_id_for_orchestration(stage.stage)
        return ProductStageTruth(
            stage_id=stage_id,
            source="orchestration",
            orchestration_stage=stage.stage.value,
        )
    return None


def resolve_product_stage_truth(
    session: SessionLike,
    project_id: UUID,
    *,
    presentation_stage_id: str,
) -> ProductStageTruth:
    """SSOT for main chrome: prefer active orchestration, else presentation heuristic."""
    session = session_of(session)
    orch = active_orchestration_product_stage(session, project_id)
    if orch is not None:
        return orch
    stage = (presentation_stage_id or "").strip() or "materials"
    if stage not in PRIMARY_STAGE_IDS:
        stage = "materials"
    return ProductStageTruth(stage_id=stage, source="presentation")
