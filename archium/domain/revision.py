"""Unified entity revision history models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, utc_now
from archium.domain.enums import RevisionEntityType, RevisionSource


class EntityRevision(IdentifiedModel):
    """Point-in-time snapshot for any revision-tracked entity."""

    entity_type: RevisionEntityType
    entity_id: UUID | None = None
    lineage_id: UUID
    presentation_id: UUID | None = None
    revision_number: int = Field(ge=1)
    change_source: RevisionSource
    snapshot: dict[str, object] = Field(default_factory=dict)
    note: str | None = None
    actor: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def slide_id(self) -> UUID | None:
        if self.entity_type == RevisionEntityType.SLIDE:
            return self.entity_id
        return None


LineageStatus = Literal["current", "replaced", "historical"]


@dataclass(frozen=True)
class SlideLineageOption:
    """Selectable slide version chain for revision UI."""

    lineage_id: UUID
    label: str
    status: LineageStatus
    logical_key: str
    current_slide_id: UUID | None
    latest_revision_number: int
