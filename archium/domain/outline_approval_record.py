"""Outline approval audit record — who approved which revision/hash."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel, utc_now


class OutlineApprovalRecord(IdentifiedModel, TimestampedModel):
    """One durable approval event for an OutlinePlan revision."""

    outline_id: UUID
    presentation_id: UUID
    project_id: UUID
    outline_revision: int = Field(ge=1)
    outline_hash: str = Field(min_length=1, max_length=128)
    approved_by: str = Field(min_length=1, max_length=200)
    approved_at: datetime = Field(default_factory=utc_now)
    superseded_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.superseded_at is None
