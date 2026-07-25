"""Unit tests for post–plan-approval workstream execution hook."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from archium.application.orchestration.workstream_execution_service import (
    WorkstreamExecutionResult,
)
from archium.application.planning_workflow_service import (
    PlanningWorkflowResult,
    PlanningWorkflowService,
)
from archium.domain.enums import PlanningSessionStatus, WorkflowStatus, WorkstreamStatus
from archium.domain.planning_session import PlanningSession
from archium.domain.workflow import WorkflowRun
from archium.domain.workstream import Workstream


def _result_with_run(run: WorkflowRun) -> PlanningWorkflowResult:
    return PlanningWorkflowResult(
        planning_session=PlanningSession(
            project_id=run.project_id,
            status=PlanningSessionStatus.READY,
        ),
        workflow_run=run,
    )


def test_workstream_hook_runs_and_attaches_child_id(monkeypatch) -> None:
    project_id = uuid4()
    mission_id = uuid4()
    run = WorkflowRun(
        project_id=project_id,
        status=WorkflowStatus.COMPLETED,
        state={"mission_id": str(mission_id), "workflow_kind": "planning"},
    )
    ws = Workstream(
        project_id=project_id,
        mission_id=mission_id,
        title="历史研究",
        objective="梳理历史依据",
        selected=True,
        status=WorkstreamStatus.SELECTED,
    )
    child = WorkflowRun(
        project_id=project_id,
        status=WorkflowStatus.COMPLETED,
        state={"workflow_kind": "workstream_execution"},
    )

    service = PlanningWorkflowService(MagicMock(), MagicMock())
    service._checkpointer_manager = MagicMock()  # noqa: SLF001

    missions = MagicMock()
    missions.list_workstreams.return_value = [ws]
    monkeypatch.setattr(
        "archium.application.planning_workflow_service.MissionRepository",
        lambda _session: missions,
    )

    fake_exec = MagicMock()
    fake_exec.run_for_mission.return_value = WorkstreamExecutionResult(
        workflow_run=child,
        completed=1,
        skipped=0,
        failed=0,
    )

    class FakeExecService:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            pass

        def run_for_mission(self, mid, workstreams):  # noqa: ANN001
            return fake_exec.run_for_mission(mid, workstreams)

    monkeypatch.setattr(
        "archium.application.orchestration.workstream_execution_service.WorkstreamExecutionService",
        FakeExecService,
    )

    updated = []

    class FakeRuns:
        def update(self, r: WorkflowRun) -> WorkflowRun:
            updated.append(r)
            return r

    service._workflow_runs = FakeRuns()  # noqa: SLF001

    out = service._run_workstream_execution_after_plan(_result_with_run(run))  # noqa: SLF001
    assert out.workflow_run.state["workstream_execution_run_id"] == str(child.id)
    assert any("已执行工作路径" in w for w in out.warnings)
    fake_exec.run_for_mission.assert_called_once()
    missions.save_workstream.assert_called()


def test_workstream_hook_skips_when_none_selected(monkeypatch) -> None:
    project_id = uuid4()
    mission_id = uuid4()
    run = WorkflowRun(
        project_id=project_id,
        status=WorkflowStatus.COMPLETED,
        state={"mission_id": str(mission_id)},
    )
    service = PlanningWorkflowService(MagicMock(), MagicMock())
    missions = MagicMock()
    missions.list_workstreams.return_value = []
    monkeypatch.setattr(
        "archium.application.planning_workflow_service.MissionRepository",
        lambda _session: missions,
    )
    out = service._run_workstream_execution_after_plan(_result_with_run(run))  # noqa: SLF001
    assert any("跳过工作路径执行" in w for w in out.warnings)
