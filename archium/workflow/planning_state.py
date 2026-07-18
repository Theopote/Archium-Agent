"""LangGraph state for project mission planning workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

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


class PlanningWorkflowState(TypedDict, total=False):
    """Mutable graph state for mission → workstream → deliverable planning."""

    workflow_kind: str
    project_id: str
    planning_session_id: str
    presentation_id: str | None
    workflow_run_id: str
    user_task_description: str
    project_name: str | None
    project_context: str
    mission_id: str | None
    mission: ProjectMission | None
    knowledge_gaps: list[KnowledgeGap]
    assumptions: list[Assumption]
    clarifying_questions: list[ClarifyingQuestion]
    design_questions: list[DesignQuestion]
    workstreams: list[Workstream]
    deliverable_plan: DeliverablePlan | None
    presentation_request_draft: dict[str, Any] | None
    artifact_execution_plans: list[dict[str, Any]]
    require_clarification: bool
    require_mission_approval: bool
    require_plan_approval: bool
    review_gate: str | None
    current_step: str
    errors: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]
    mission_validation: dict[str, Any] | None


def initial_planning_state(
    *,
    project_id: str,
    workflow_run_id: str,
    planning_session_id: str,
    user_task_description: str,
    presentation_id: str | None = None,
    require_clarification: bool = True,
    require_mission_approval: bool = True,
    require_plan_approval: bool = True,
) -> PlanningWorkflowState:
    return {
        "workflow_kind": "planning",
        "project_id": project_id,
        "planning_session_id": planning_session_id,
        "presentation_id": presentation_id,
        "workflow_run_id": workflow_run_id,
        "user_task_description": user_task_description,
        "project_name": None,
        "project_context": "",
        "mission_id": None,
        "mission": None,
        "knowledge_gaps": [],
        "assumptions": [],
        "clarifying_questions": [],
        "design_questions": [],
        "workstreams": [],
        "deliverable_plan": None,
        "presentation_request_draft": None,
        "artifact_execution_plans": [],
        "require_clarification": require_clarification,
        "require_mission_approval": require_mission_approval,
        "require_plan_approval": require_plan_approval,
        "review_gate": None,
        "current_step": WorkflowStep.INIT.value,
        "errors": [],
        "warnings": [],
        "mission_validation": None,
    }
