"""Serialize planning workflow state for WorkflowRun persistence."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from archium.domain.deliverable import DeliverablePlan
from archium.domain.enums import WorkflowStep
from archium.domain.knowledge_gap import (
    Assumption,
    ClarifyingQuestion,
    DesignQuestion,
    KnowledgeGap,
)
from archium.domain.project_mission import ProjectMission
from archium.domain.workstream import Workstream
from archium.workflow.planning_state import PlanningWorkflowState


def snapshot_planning_state(state: PlanningWorkflowState) -> dict[str, Any]:
    mission = state.get("mission")
    plan = state.get("deliverable_plan")
    return {
        "workflow_kind": "planning",
        "current_step": state.get("current_step", WorkflowStep.INIT.value),
        "project_id": state.get("project_id"),
        "planning_session_id": state.get("planning_session_id"),
        "presentation_id": state.get("presentation_id"),
        "workflow_run_id": state.get("workflow_run_id"),
        "user_task_description": state.get("user_task_description", ""),
        "project_name": state.get("project_name"),
        "project_context": state.get("project_context", ""),
        "mission_id": state.get("mission_id") or (str(mission.id) if mission is not None else None),
        "mission": mission.model_dump(mode="json") if mission is not None else None,
        "knowledge_gaps": [item.model_dump(mode="json") for item in state.get("knowledge_gaps", [])],
        "assumptions": [item.model_dump(mode="json") for item in state.get("assumptions", [])],
        "clarifying_questions": [
            item.model_dump(mode="json") for item in state.get("clarifying_questions", [])
        ],
        "design_questions": [
            item.model_dump(mode="json") for item in state.get("design_questions", [])
        ],
        "workstreams": [item.model_dump(mode="json") for item in state.get("workstreams", [])],
        "deliverable_plan": plan.model_dump(mode="json") if plan is not None else None,
        "presentation_request_draft": state.get("presentation_request_draft"),
        "artifact_execution_plans": list(state.get("artifact_execution_plans") or []),
        "require_clarification": state.get("require_clarification", True),
        "require_mission_approval": state.get("require_mission_approval", True),
        "require_plan_approval": state.get("require_plan_approval", True),
        "review_gate": state.get("review_gate"),
        "needs_mission_correction": bool(state.get("needs_mission_correction", False)),
        "mission_validation_phase": state.get("mission_validation_phase"),
        "errors": list(state.get("errors", [])),
        "warnings": list(state.get("warnings", [])),
        "mission_validation": state.get("mission_validation"),
    }


def restore_planning_artifacts(state_data: dict[str, Any]) -> dict[str, Any]:
    restored = dict(state_data)
    if state_data.get("mission"):
        restored["mission"] = ProjectMission.model_validate(state_data["mission"])
    if state_data.get("knowledge_gaps"):
        restored["knowledge_gaps"] = [
            KnowledgeGap.model_validate(item) for item in state_data["knowledge_gaps"]
        ]
    if state_data.get("assumptions"):
        restored["assumptions"] = [
            Assumption.model_validate(item) for item in state_data["assumptions"]
        ]
    if state_data.get("clarifying_questions"):
        restored["clarifying_questions"] = [
            ClarifyingQuestion.model_validate(item) for item in state_data["clarifying_questions"]
        ]
    if state_data.get("design_questions"):
        restored["design_questions"] = [
            DesignQuestion.model_validate(item) for item in state_data["design_questions"]
        ]
    if state_data.get("workstreams"):
        restored["workstreams"] = [
            Workstream.model_validate(item) for item in state_data["workstreams"]
        ]
    if state_data.get("deliverable_plan"):
        restored["deliverable_plan"] = DeliverablePlan.model_validate(state_data["deliverable_plan"])
    return restored


def planning_mission_id(state: PlanningWorkflowState) -> UUID | None:
    raw = state.get("mission_id")
    if raw:
        return UUID(raw)
    mission = state.get("mission")
    return mission.id if mission is not None else None
