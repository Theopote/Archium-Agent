"""Slide revision history models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel, IdentifiedModel
from archium.domain.enums import SlideChangeSource


class SlideRevision(IdentifiedModel):
    """Point-in-time snapshot of a slide specification."""

    slide_id: UUID | None
    presentation_id: UUID
    revision_number: int = Field(ge=1)
    change_source: SlideChangeSource
    snapshot: dict[str, object] = Field(default_factory=dict)
    note: str | None = None
    created_at: datetime


class SlideFieldChange(DomainModel):
    """Single field difference between two slide snapshots."""

    field: str
    label: str
    before: str
    after: str
    unified_diff: str | None = None


class SlideDiffResult(DomainModel):
    """Comparison result between two slide snapshots."""

    slide_id: UUID | None
    presentation_id: UUID
    before_label: str
    after_label: str
    changes: list[SlideFieldChange] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)
