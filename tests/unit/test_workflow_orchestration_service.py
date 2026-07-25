"""Unit tests for WorkflowOrchestrationService start/advance (mocked children)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from archium.application.orchestration.workflow_orchestration_service import (
    ORCHESTRATION_KIND,
    WorkflowOrchestrationService,
)
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.enums import WorkflowStatus
from archium.domain.intent.next_best_action import NextBestActionType
from archium.domain.orchestration import (
    OrchestrationStage,
    OrchestrationStageStatus,
)
from archium.domain.workflow import WorkflowRun


def test_resolve_action_target_includes_orchestration_start() -> None:
    from archium.application.context.next_action_selector import resolve_action_target

    target = resolve_action_target(NextBestActionType.GENERATE_MISSION)
    assert target.orchestration_action == "start"
    assert target.stage_hint == OrchestrationStage.MISSION_PLANNING.value
    assert target.page_key == "project-mission"


def test_orchestration_start_explore_awaits_user(monkeypatch) -> None:
    session = MagicMock()
    llm = MagicMock()
    created: list[WorkflowRun] = []

    class FakeRepo:
        def create(self, run: WorkflowRun) -> WorkflowRun:
            created.append(run)
            return run

        def update(self, run: WorkflowRun) -> WorkflowRun:
            return run

        def list_by_project(self, project_id):  # noqa: ANN001
            return []

        def get_by_id(self, run_id):  # noqa: ANN001
            return created[0] if created else None

    service = WorkflowOrchestrationService(session, llm)
    service._workflow_runs = FakeRepo()  # noqa: SLF001
    service._missions = MagicMock()  # noqa: SLF001

    result = service.start(
        uuid4(),
        action=NextBestActionType.EXPLORE_DIRECTIONS,
    )
    assert result.workflow_run.state.get("workflow_kind") == ORCHESTRATION_KIND
    assert result.active_stage == OrchestrationStage.EXPLORE
    assert result.awaiting_user
    assert result.page_key == "concept-exploration"
    stage = result.plan.active_stage()
    assert stage is not None
    assert stage.status == OrchestrationStageStatus.AWAITING_USER


def test_orchestration_advance_moves_to_next_stage(monkeypatch) -> None:
    session = MagicMock()
    llm = MagicMock()
    project_id = uuid4()
    service = WorkflowOrchestrationService(session, llm)

    plan = service.build_plan(
        project_id,
        action=NextBestActionType.EXPLORE_DIRECTIONS,
    )
    # Force explore awaiting user
    plan.stages[0].status = OrchestrationStageStatus.AWAITING_USER
    run = WorkflowRun(
        project_id=project_id,
        status=WorkflowStatus.AWAITING_REVIEW,
        state={
            "workflow_kind": ORCHESTRATION_KIND,
            "orchestration_plan": plan.model_dump(mode="json"),
            "user_task_description": "",
        },
    )
    store = {run.id: run}

    class FakeRepo:
        def get_by_id(self, run_id):  # noqa: ANN001
            return store.get(run_id)

        def update(self, updated: WorkflowRun) -> WorkflowRun:
            store[updated.id] = updated
            return updated

        def list_by_project(self, _project_id):  # noqa: ANN001
            return list(store.values())

        def create(self, created: WorkflowRun) -> WorkflowRun:
            store[created.id] = created
            return created

    service._workflow_runs = FakeRepo()  # noqa: SLF001
    # Mission planning without task should await user rather than call LLM
    service._missions = MagicMock()  # noqa: SLF001
    service._missions.list_missions_by_project.return_value = []

    result = service.advance(run.id)
    # After explore completes, next is mission_planning which awaits task text
    assert result.active_stage in {
        OrchestrationStage.MISSION_PLANNING,
        OrchestrationStage.WORKSTREAM_EXECUTION,
        None,
    } or result.plan.stages[0].status == OrchestrationStageStatus.COMPLETED


def test_build_plan_mission_workflow() -> None:
    service = WorkflowOrchestrationService(MagicMock(), MagicMock())
    plan = service.build_plan(uuid4())
    # default without context → MISSION sequence
    assert plan.stages[0].stage == OrchestrationStage.MISSION_PLANNING
    assert any(s.stage == OrchestrationStage.PRESENTATION for s in plan.stages)
