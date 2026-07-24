"""Stage workflow step enums (DOM-007).

Prefer the stage-specific StrEnum for node / service code.
``WorkflowStep`` remains a derived mega-enum for persisted ``current_step``
compatibility and cross-pipeline label maps.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from archium.domain.enums.workflow_steps.planning import PlanningWorkflowStep
from archium.domain.enums.workflow_steps.presentation import PresentationWorkflowStep
from archium.domain.enums.workflow_steps.slide_recovery import SlideRecoveryWorkflowStep
from archium.domain.enums.workflow_steps.visual import VisualWorkflowStep

__all__ = [
    "PlanningWorkflowStep",
    "PresentationWorkflowStep",
    "SlideRecoveryWorkflowStep",
    "VisualWorkflowStep",
    "WORKFLOW_STEP_STAGES",
    "build_workflow_step_enum",
]

WORKFLOW_STEP_STAGES: tuple[type[StrEnum], ...] = (
    PresentationWorkflowStep,
    PlanningWorkflowStep,
    VisualWorkflowStep,
    SlideRecoveryWorkflowStep,
)


def build_workflow_step_enum() -> Any:
    """Compose the legacy mega-enum from stage enums (identical string values)."""
    members: dict[str, str] = {}
    for stage in WORKFLOW_STEP_STAGES:
        for member in stage:
            existing = members.get(member.name)
            if existing is not None and existing != member.value:
                raise RuntimeError(
                    f"workflow step name conflict: {member.name} "
                    f"({existing!r} vs {member.value!r})"
                )
            members[member.name] = member.value
    return StrEnum("WorkflowStep", members)
