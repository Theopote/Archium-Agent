"""Project domain model."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.enums import ProjectOriginMode, ProjectStage, ProjectStatus, ProjectType
from archium.domain.intent.intent_evolution import IntentEvolution
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.intent.knowledge_state_history import KnowledgeStateHistory


class Project(IdentifiedModel, TimestampedModel):
    """Unique architectural project identity root (DOM-023).

    Satellites (Mission, Facts, Presentations, …) reference ``project_id``;
    do not nest them into this model or invent a parallel Project identity.
    See ``archium.domain.project_aggregate_map`` and
    ``docs/architecture/current-system.md`` § Project Aggregate Map.
    """

    name: str = Field(min_length=1, max_length=500)
    code: str | None = Field(default=None, max_length=100)
    description: str | None = None
    project_type: ProjectType = ProjectType.OTHER
    stage: ProjectStage = ProjectStage.CONCEPT
    location: str | None = None
    client: str | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    origin_mode: ProjectOriginMode = ProjectOriginMode.EXISTING_PROJECT
    organization_id: UUID | None = Field(
        default=None,
        description="Optional tenant root (DOM-032); null = local / unscoped.",
    )
    knowledge_state: KnowledgeState | None = None
    knowledge_state_history: KnowledgeStateHistory = Field(
        default_factory=KnowledgeStateHistory
    )
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
