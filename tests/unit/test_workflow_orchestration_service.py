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
    OrchestrationPlan,
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


def test_presentation_stage_awaits_when_planning_ready() -> None:
    service = WorkflowOrchestrationService(MagicMock(), MagicMock())
    project_id = uuid4()
    planning = WorkflowRun(
        project_id=project_id,
        status=WorkflowStatus.COMPLETED,
        state={
            "workflow_kind": "planning",
            "presentation_request_draft": {"mission_id": str(uuid4())},
        },
    )

    class FakeRepo:
        def list_by_project(self, _pid):  # noqa: ANN001
            return [planning]

    service._workflow_runs = FakeRepo()  # noqa: SLF001
    # Avoid real prepare_run — exercise fallback warning path via monkeypatch
    service._prepare_presentation_from_planning = (  # noqa: SLF001
        lambda _pid, planning_run: {
            "status": OrchestrationStageStatus.AWAITING_USER,
            "workflow_run_id": planning_run.id,
            "warnings": ["已通过 PresentationWorkflowService.prepare_run 创建汇报运行"],
        }
    )
    out = service._run_presentation_stage(project_id)  # noqa: SLF001
    assert out["status"] == OrchestrationStageStatus.AWAITING_USER
    assert out["workflow_run_id"] == planning.id


def test_presentation_stage_reuses_existing_pipeline_run() -> None:
    service = WorkflowOrchestrationService(MagicMock(), MagicMock())
    project_id = uuid4()
    child = WorkflowRun(
        project_id=project_id,
        presentation_id=uuid4(),
        status=WorkflowStatus.AWAITING_REVIEW,
        state={"request": {"title": "概念汇报"}, "current_step": "outline"},
    )

    class FakeRepo:
        def list_by_project(self, _pid):  # noqa: ANN001
            return [child]

    service._workflow_runs = FakeRepo()  # noqa: SLF001
    out = service._run_presentation_stage(project_id)  # noqa: SLF001
    assert out["status"] == OrchestrationStageStatus.AWAITING_REVIEW
    assert out["workflow_run_id"] == child.id


def test_visual_stage_skips_without_presentation(monkeypatch) -> None:
    service = WorkflowOrchestrationService(MagicMock(), MagicMock())
    project_id = uuid4()

    class FakeRepo:
        def list_by_project(self, _pid):  # noqa: ANN001
            return []

    service._workflow_runs = FakeRepo()  # noqa: SLF001

    class FakePresRepo:
        def __init__(self, _session):  # noqa: ANN001
            pass

        def list_by_project(self, _pid):  # noqa: ANN001
            return []

    monkeypatch.setattr(
        "archium.infrastructure.database.repositories.PresentationRepository",
        FakePresRepo,
    )
    out = service._run_visual_stage(project_id)  # noqa: SLF001
    assert out["status"] == OrchestrationStageStatus.SKIPPED


def test_link_child_run_attaches_to_active_presentation_stage() -> None:
    service = WorkflowOrchestrationService(MagicMock(), MagicMock())
    project_id = uuid4()
    plan = service.build_plan(project_id)
    # Jump to presentation stage
    for stage in plan.stages:
        if stage.stage != OrchestrationStage.PRESENTATION:
            stage.status = OrchestrationStageStatus.COMPLETED
        else:
            stage.status = OrchestrationStageStatus.AWAITING_USER
            break
    plan.active_index = next(
        i
        for i, s in enumerate(plan.stages)
        if s.stage == OrchestrationStage.PRESENTATION
    )
    run = WorkflowRun(
        project_id=project_id,
        status=WorkflowStatus.AWAITING_REVIEW,
        state={
            "workflow_kind": ORCHESTRATION_KIND,
            "orchestration_plan": plan.model_dump(mode="json"),
        },
    )
    store = {run.id: run}

    class FakeRepo:
        def list_by_project(self, _pid):  # noqa: ANN001
            return [run]

        def get_by_id(self, rid):  # noqa: ANN001
            return store.get(rid)

        def update(self, updated: WorkflowRun) -> WorkflowRun:
            store[updated.id] = updated
            return updated

    service._workflow_runs = FakeRepo()  # noqa: SLF001
    child_id = uuid4()
    linked = service.link_child_run(
        project_id,
        stage=OrchestrationStage.PRESENTATION,
        child_workflow_run_id=child_id,
    )
    assert linked is not None
    refreshed = OrchestrationPlan.model_validate(
        linked.state["orchestration_plan"]
    )
    active = refreshed.active_stage()
    assert active is not None
    assert active.workflow_run_id == child_id
    assert active.status == OrchestrationStageStatus.AWAITING_REVIEW


def test_workstream_stage_skips_when_already_completed() -> None:
    from archium.domain.enums import WorkstreamStatus
    from archium.domain.workstream import Workstream

    service = WorkflowOrchestrationService(MagicMock(), MagicMock())
    project_id = uuid4()
    mission = MagicMock()
    mission.id = uuid4()
    ws = Workstream(
        project_id=project_id,
        mission_id=mission.id,
        title="历史研究",
        objective="梳理历史依据",
        selected=True,
        status=WorkstreamStatus.COMPLETED,
    )
    service._missions = MagicMock()  # noqa: SLF001
    service._missions.list_missions_by_project.return_value = [mission]
    service._missions.list_workstreams.return_value = [ws]

    out = service._run_workstream_stage(project_id)  # noqa: SLF001
    assert out["status"] == OrchestrationStageStatus.COMPLETED
    assert "此前已执行" in (out.get("warnings") or [""])[0]
