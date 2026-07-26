"""Project event log — unified design memory across Intent / process / deliverables.

Not full Event Sourcing: append-only projection + explicit emits that sit beside
IntentEvolution / KnowledgeStateHistory / process_timeline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel


class ProjectEventType(StrEnum):
    """Coarse product events architects can read as design memory."""

    PROJECT_CREATED = "project_created"
    CONTEXT_UPDATED = "context_updated"
    MISSION_CHANGED = "mission_changed"
    INTENT_CHANGED = "intent_changed"
    CONCEPT_SELECTED = "concept_selected"
    RESEARCH_COMPLETED = "research_completed"
    DESIGN_REVISED = "design_revised"
    DESIGN_CRITIQUE = "design_critique"
    DESIGN_DECISION = "design_decision"
    REFLECTION = "reflection"
    VISUAL_FEEDBACK = "visual_feedback"
    PRESENTATION_GENERATED = "presentation_generated"
    PROCESS_CHECKPOINT = "process_checkpoint"
    OTHER = "other"


class ProjectEventActor(StrEnum):
    USER = "user"
    SYSTEM = "system"
    AI = "ai"


# Payload key for member-level attribution (COLLAB-006). Avoids schema migration.
MEMBER_ACTOR_ID_KEY = "actor_id"


class ProjectEvent(IdentifiedModel, TimestampedModel):
    """One append-only project memory row."""

    project_id: UUID
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: ProjectEventActor = ProjectEventActor.SYSTEM
    event_type: ProjectEventType = ProjectEventType.OTHER
    summary: str = Field(min_length=1, max_length=800)
    payload: dict[str, Any] = Field(default_factory=dict)
    # Idempotency for projections (intent / process timeline)
    dedupe_key: str = Field(default="", max_length=200)
    source: str = Field(default="", max_length=80)

    @property
    def member_actor_id(self) -> str | None:
        raw = self.payload.get(MEMBER_ACTOR_ID_KEY)
        if raw is None:
            return None
        text = str(raw).strip()
        return text[:200] or None

    def display_line(self) -> str:
        return self.summary.strip()

    def attribution_label(self) -> str:
        """Short 「谁」label for UI; empty when unattributed."""
        member = self.member_actor_id
        if member:
            return member
        if self.actor == ProjectEventActor.USER:
            return "用户"
        if self.actor == ProjectEventActor.AI:
            return "AI"
        return ""
