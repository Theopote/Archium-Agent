"""Mission-first planning workflow steps (DOM-007)."""

from enum import StrEnum


class PlanningWorkflowStep(StrEnum):
    PLANNING_LOAD_CONTEXT = "planning_load_context"
    PLANNING_ANALYZE_TASK = "planning_analyze_task"
    PLANNING_AUTONOMOUS_RESEARCH = "planning_autonomous_research"
    PLANNING_VALIDATE_MISSION = "planning_validate_mission"
    PLANNING_AWAIT_MISSION_CORRECTION = "planning_await_mission_correction"
    PLANNING_AWAIT_CLARIFICATION = "planning_await_clarification"
    PLANNING_REVISE_MISSION = "planning_revise_mission"
    PLANNING_VALIDATE_REVISED_MISSION = "planning_validate_revised_mission"
    PLANNING_AWAIT_MISSION_APPROVAL = "planning_await_mission_approval"
    PLANNING_WORKSTREAMS = "planning_workstreams"
    PLANNING_DELIVERABLES = "planning_deliverables"
    PLANNING_AWAIT_APPROVAL = "planning_await_approval"
    PLANNING_PREPARE_ARTIFACTS = "planning_prepare_artifacts"
    # Legacy alias — old checkpoints may still store this string.
    PLANNING_PREPARE_PRESENTATION = "planning_prepare_presentation"
    PLANNING_FINALIZE = "planning_finalize"
