"""Exploration session — concept directions before Mission commitment."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, model_validator

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.enums import ExplorationSessionStatus
from archium.domain.intent.idea_seed import IdeaSeed


class ExplorationSession(IdentifiedModel, TimestampedModel):
    """One idea-seed exploration that may produce ConceptDirections then a Mission."""

    project_id: UUID
    idea_text: str = Field(min_length=1)
    idea_seed: IdeaSeed | None = None
    status: ExplorationSessionStatus = ExplorationSessionStatus.EXPLORING
    selected_direction_id: UUID | None = None
    mission_id: UUID | None = None
    source: str = Field(default="genesis", max_length=40)

    @model_validator(mode="after")
    def _sync_idea_seed(self) -> ExplorationSession:
        if self.idea_seed is None:
            object.__setattr__(
                self,
                "idea_seed",
                IdeaSeed.from_raw(self.idea_text, source="legacy"),
            )
        elif self.idea_text.strip() != self.idea_seed.raw_input.strip():
            # Prefer idea_seed.raw_input as authority when both present.
            object.__setattr__(self, "idea_text", self.idea_seed.raw_input.strip())
        return self

    def mark_direction_selected(self, direction_id: UUID) -> None:
        self.selected_direction_id = direction_id
        self.status = ExplorationSessionStatus.DIRECTION_SELECTED
        self.touch()

    def mark_committed(self, mission_id: UUID) -> None:
        self.mission_id = mission_id
        self.status = ExplorationSessionStatus.COMMITTED
        self.touch()
