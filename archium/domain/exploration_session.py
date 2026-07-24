"""Exploration session — concept directions before Mission commitment."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.enums import ExplorationSessionStatus


class ExplorationSession(IdentifiedModel, TimestampedModel):
    """One idea-seed exploration that may produce ConceptDirections then a Mission."""

    project_id: UUID
    idea_text: str = Field(min_length=1)
    status: ExplorationSessionStatus = ExplorationSessionStatus.EXPLORING
    selected_direction_id: UUID | None = None
    mission_id: UUID | None = None
    source: str = Field(default="genesis", max_length=40)

    def mark_direction_selected(self, direction_id: UUID) -> None:
        self.selected_direction_id = direction_id
        self.status = ExplorationSessionStatus.DIRECTION_SELECTED
        self.touch()

    def mark_committed(self, mission_id: UUID) -> None:
        self.mission_id = mission_id
        self.status = ExplorationSessionStatus.COMMITTED
        self.touch()
