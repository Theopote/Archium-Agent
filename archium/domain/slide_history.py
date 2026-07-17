"""Slide revision history models."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.revision import EntityRevision, SlideLineageOption

# Backward-compatible alias; slide history uses the unified revision model.
SlideRevision = EntityRevision

__all__ = [
    "SlideDiffResult",
    "SlideFieldChange",
    "SlideLineageOption",
    "SlideRevision",
]


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
