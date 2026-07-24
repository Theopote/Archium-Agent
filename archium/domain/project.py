"""Project domain model."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.enums import ProjectOriginMode, ProjectStage, ProjectStatus, ProjectType
from archium.domain.intent.intent_evolution import IntentEvolution
from archium.domain.intent.knowledge_state import KnowledgeState


class Project(IdentifiedModel, TimestampedModel):
    """A building or planning project that owns documents and presentations."""

    name: str = Field(min_length=1, max_length=500)
    code: str | None = Field(default=None, max_length=100)
    description: str | None = None
    project_type: ProjectType = ProjectType.OTHER
    stage: ProjectStage = ProjectStage.CONCEPT
    location: str | None = None
    client: str | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    origin_mode: ProjectOriginMode = ProjectOriginMode.EXISTING_PROJECT
    knowledge_state: KnowledgeState | None = None
    intent_evolution: IntentEvolution = Field(default_factory=IntentEvolution)

    def archive(self) -> None:
        """Mark the project as archived."""
        self.status = ProjectStatus.ARCHIVED
        self.touch()

    def mark_deleting(self) -> None:
        """Mark the project as mid-deletion (hidden from normal listings)."""
        self.status = ProjectStatus.DELETING
        self.touch()

    def touch(self) -> None:
        """Update the modification timestamp."""
        TimestampedModel.touch(self)
