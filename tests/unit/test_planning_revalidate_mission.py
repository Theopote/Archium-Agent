"""Tests for post-revision mission revalidation and correction routing."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from archium.application.mission_validation_service import MissionValidationService
from archium.domain.enums import WorkflowStep
from archium.domain.project_mission import ProjectMission
from archium.workflow.planning_graph import (
    _route_after_initial_validation,
    _route_after_mission_correction,
    _route_after_mission_revision,
    _route_after_revised_validation,
)
from archium.workflow.planning_nodes import PlanningWorkflowNodes
from archium.workflow.planning_state import PlanningWorkflowState


def test_revise_routes_to_revalidate_not_approval() -> None:
    assert _route_after_mission_revision({}) == "validate_revised_mission"
    assert _route_after_mission_revision({"errors": ["x"]}) == "finalize"


def test_revised_validation_routes_to_mission_approval_when_ok() -> None:
    assert _route_after_revised_validation({}) == "await_mission_approval"
    assert _route_after_revised_validation({"errors": ["x"]}) == "finalize"
    assert (
        _route_after_revised_validation({"needs_mission_correction": True})
        == "await_mission_correction"
    )


def test_initial_validation_routes_to_correction_or_clarification() -> None:
    assert _route_after_initial_validation({}) == "await_user_clarification"
    assert (
        _route_after_initial_validation({"needs_mission_correction": True})
        == "await_mission_correction"
    )
    assert _route_after_initial_validation({"errors": ["x"]}) == "finalize"


def test_correction_routes_by_phase() -> None:
    assert _route_after_mission_correction({}) == "await_user_clarification"
    assert (
        _route_after_mission_correction({"mission_validation_phase": "revised"})
        == "await_mission_approval"
    )
    assert (
        _route_after_mission_correction({"needs_mission_correction": True})
        == "await_mission_correction"
    )
    assert _route_after_mission_correction({"errors": ["x"]}) == "finalize"


def test_validate_revised_mission_marks_recoverable_empty_task_natures() -> None:
    project_id = uuid4()
    mission = ProjectMission(
        project_id=project_id,
        title="修订后任务",
        task_statement="只做低碳专项建议",
        task_natures=[],
        in_scope=["诊断"],
        out_of_scope=["施工图"],
    )
    persisted: list[object] = []

    def _persist(merged: object, status: object = None) -> None:
        persisted.append((merged, status))

    runtime = SimpleNamespace(
        facts=SimpleNamespace(list_by_project=lambda _pid: []),
        mission_validator=MissionValidationService(),
        mission_service=SimpleNamespace(
            get_mission_bundle=lambda _mid: SimpleNamespace(
                mission=mission,
                knowledge_gaps=[],
                clarifying_questions=[],
                design_questions=[],
                assumptions=[],
            )
        ),
        workflow_runs=SimpleNamespace(get_by_id=lambda _rid: None),
    )
    nodes = PlanningWorkflowNodes(runtime)  # type: ignore[arg-type]
    nodes._persist = _persist  # type: ignore[method-assign]
    state: PlanningWorkflowState = {
        "project_id": str(project_id),
        "workflow_run_id": str(uuid4()),
        "mission_id": str(mission.id),
        "mission": mission,
        "knowledge_gaps": [],
        "clarifying_questions": [],
        "warnings": [],
        "errors": [],
    }
    result = nodes.validate_revised_mission(state)
    assert result["current_step"] == WorkflowStep.PLANNING_VALIDATE_REVISED_MISSION.value
    assert not result.get("errors")
    assert result.get("needs_mission_correction") is True
    assert result.get("mission_validation_phase") == "revised"
    assert result.get("mission_validation", {}).get("needs_correction") is True
    assert any("task_natures" in err for err in result.get("warnings", []))
    assert persisted


def test_validate_revised_mission_passes_consistent_mission() -> None:
    from archium.domain.enums import ServiceDepth, TaskNature
    from archium.domain.project_mission import EvaluationCriterion, Stakeholder

    project_id = uuid4()
    mission = ProjectMission(
        project_id=project_id,
        title="低碳专项",
        task_statement="园区绿色低碳专项建议",
        task_natures=[TaskNature.CONSULTING],
        requested_service_depths=[ServiceDepth.PROJECT_DIAGNOSIS],
        in_scope=["目标体系"],
        out_of_scope=["施工图"],
        stakeholders=[Stakeholder(name="园区运营", role="业主", concerns=["碳强度"])],
        decisions_required=["是否分期实施"],
        design_questions=["如何在不停产前提下推进低碳改造？"],
        evaluation_criteria=[
            EvaluationCriterion(name="可实施性", description="能否分期落地"),
        ],
        confidence=0.55,
        key_unknowns=["改造预算"],
    )
    persisted: list[object] = []

    def _persist(merged: object, status: object = None) -> None:
        persisted.append((merged, status))

    runtime = SimpleNamespace(
        facts=SimpleNamespace(list_by_project=lambda _pid: []),
        mission_validator=MissionValidationService(),
        mission_service=SimpleNamespace(
            get_mission_bundle=lambda _mid: SimpleNamespace(
                mission=mission,
                knowledge_gaps=[],
                clarifying_questions=[],
                design_questions=[],
                assumptions=[],
            )
        ),
        workflow_runs=SimpleNamespace(get_by_id=lambda _rid: None),
    )
    nodes = PlanningWorkflowNodes(runtime)  # type: ignore[arg-type]
    nodes._persist = _persist  # type: ignore[method-assign]
    state: PlanningWorkflowState = {
        "project_id": str(project_id),
        "workflow_run_id": str(uuid4()),
        "mission_id": str(mission.id),
        "mission": mission,
        "knowledge_gaps": [],
        "clarifying_questions": [],
        "warnings": [],
        "errors": [],
    }
    result = nodes.validate_revised_mission(state)
    assert result["current_step"] == WorkflowStep.PLANNING_VALIDATE_REVISED_MISSION.value
    assert not result.get("errors")
    assert result.get("needs_mission_correction") is False
    assert result.get("mission_validation", {}).get("ok") is True
    assert persisted


def test_validate_mission_missing_mission_is_fatal() -> None:
    nodes = PlanningWorkflowNodes(SimpleNamespace())  # type: ignore[arg-type]
    result = nodes.validate_mission(
        {
            "project_id": str(uuid4()),
            "workflow_run_id": str(uuid4()),
            "mission": None,
        }
    )
    assert result["current_step"] == WorkflowStep.FAILED.value
    assert result.get("errors")
    assert result.get("needs_mission_correction") is False
