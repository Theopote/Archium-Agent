"""Topic 07 WF-010 — single product-stage truth."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from archium.application.product_stage_truth import (
    product_stage_id_for_orchestration,
    resolve_product_stage_truth,
)
from archium.domain.enums import EvidenceAvailability, WorkflowStatus
from archium.domain.orchestration import (
    OrchestrationPlan,
    OrchestrationStage,
    OrchestrationStageSpec,
    OrchestrationStageStatus,
)
from archium.domain.project import Project
from archium.domain.workflow import WorkflowRun
from archium.infrastructure.database.repositories import (
    ProjectRepository,
    WorkflowRunRepository,
)
from archium.ui.project_progress_card import ProjectProgressSnapshot


def test_orchestration_maps_onto_five_stages() -> None:
    assert product_stage_id_for_orchestration(OrchestrationStage.EXPLORE) == "outline"
    assert product_stage_id_for_orchestration(OrchestrationStage.MATERIALS) == "materials"
    assert (
        product_stage_id_for_orchestration(OrchestrationStage.PRESENTATION) == "generate"
    )
    assert product_stage_id_for_orchestration(OrchestrationStage.VISUAL) == "edit"
    assert product_stage_id_for_orchestration(OrchestrationStage.DELIVER) == "deliver"


def test_resolve_prefers_active_orchestration(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="双轨项目"))
    plan = OrchestrationPlan(
        project_id=project.id,
        stages=[
            OrchestrationStageSpec(
                stage=OrchestrationStage.MISSION_PLANNING,
                status=OrchestrationStageStatus.AWAITING_USER,
            )
        ],
        active_index=0,
    )
    WorkflowRunRepository(db_session).create(
        WorkflowRun(
            project_id=project.id,
            status=WorkflowStatus.AWAITING_REVIEW,
            state={
                "workflow_kind": "orchestration",
                "orchestration_plan": plan.model_dump(mode="json"),
            },
        )
    )
    db_session.flush()

    truth = resolve_product_stage_truth(
        db_session,
        project.id,
        presentation_stage_id="generate",
    )
    assert truth.source == "orchestration"
    assert truth.stage_id == "outline"
    assert truth.orchestration_stage == "mission_planning"


def test_resolve_falls_back_to_presentation(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="无编排"))
    truth = resolve_product_stage_truth(
        db_session,
        project.id,
        presentation_stage_id="deliver",
    )
    assert truth.source == "presentation"
    assert truth.stage_id == "deliver"


def test_snapshot_authoritative_overrides_heuristic() -> None:
    snap = ProjectProgressSnapshot(
        project_id=uuid4(),
        project_name="权威阶段",
        presentation_id=None,
        presentation_title=None,
        presentation_type=None,
        document_count=0,
        slide_count=0,
        layout_ready_count=0,
        has_brief=False,
        ready_for_export=False,
        updated_at=datetime.now(UTC),
        evidence_availability=EvidenceAvailability.MISSING,
        authoritative_stage_id="outline",
    )
    assert snap.presentation_heuristic_stage_id() == "materials"
    assert snap.current_stage_id == "outline"
    assert snap.current_stage_label == "大纲"
