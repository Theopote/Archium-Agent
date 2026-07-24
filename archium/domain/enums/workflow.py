"""Domain enumerations — workflow bounded context (DOM-018 / DOM-007)."""

from enum import StrEnum
from typing import Any

from archium.domain.enums.workflow_steps import (
    PlanningWorkflowStep,
    PresentationWorkflowStep,
    SlideRecoveryWorkflowStep,
    VisualWorkflowStep,
    build_workflow_step_enum,
)


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PlanningSessionStatus(StrEnum):
    """Lifecycle of a mission-first planning session (not a Presentation)."""

    DRAFT = "draft"
    CLARIFYING = "clarifying"
    PLANNING = "planning"
    AWAITING_MISSION_CORRECTION = "awaiting_mission_correction"
    AWAITING_MISSION_APPROVAL = "awaiting_mission_approval"
    AWAITING_APPROVAL = "awaiting_approval"
    READY = "ready"
    COMPLETED = "completed"
    FAILED = "failed"

# Derived mega-enum for persisted current_step + cross-pipeline maps (DOM-007).
# Prefer stage-specific enums in graph nodes / services.
# Typed as Any so mypy accepts dynamic StrEnum members as a concrete type.
WorkflowStep: Any = build_workflow_step_enum()

__all__ = [
    "WorkflowStatus",
    "PlanningSessionStatus",
    "WorkflowStep",
    "PresentationWorkflowStep",
    "PlanningWorkflowStep",
    "VisualWorkflowStep",
    "SlideRecoveryWorkflowStep",
]
