"""Planning session — first-class identity for mission-first planning."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.enums import PlanningSessionStatus, ProjectOriginMode


class PlanningSession(IdentifiedModel, TimestampedModel):
    """Tracks a planning effort independent of Presentation artifacts."""

    project_id: UUID
    status: PlanningSessionStatus = PlanningSessionStatus.DRAFT
    current_mission_id: UUID | None = None
    workflow_run_id: UUID | None = None
    presentation_id: UUID | None = None
    user_task_description: str = Field(default="", max_length=20000)
    origin_mode: ProjectOriginMode = ProjectOriginMode.EXISTING_PROJECT

    def touch(self) -> None:
        TimestampedModel.touch(self)
