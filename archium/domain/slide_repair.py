"""Slide auto-repair audit records."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.enums import SlideRepairTier


class SlideRepairRecord(DomainModel):
    """Audit trail for an automated slide repair action."""

    presentation_id: UUID
    slide_id: UUID
    tier: SlideRepairTier
    before_message: str
    after_message: str
    before_key_points: list[str] = Field(default_factory=list)
    after_key_points: list[str] = Field(default_factory=list)
    removed_items: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    involves_citation: bool = False
    involves_numbers: bool = False
    requires_manual_confirmation: bool = False
    split_slide_id: UUID | None = None
    issue_ids: list[UUID] = Field(default_factory=list)
