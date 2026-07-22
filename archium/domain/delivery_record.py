"""Delivery export record — persisted export history for home / deliver."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel, utc_now


class DeliveryRecord(IdentifiedModel, TimestampedModel):
    """One exported artifact (PPTX/PDF) for a presentation."""

    project_id: UUID
    presentation_id: UUID
    revision_id: UUID | None = None
    format: str = Field(min_length=1, max_length=40)
    file_uri: str = Field(min_length=1, max_length=2000)
    file_hash: str = Field(default="", max_length=128)
    qa_status: str = Field(default="unknown", max_length=40)
    round_trip_report_json: dict[str, object] | None = None
    exported_at: datetime = Field(default_factory=utc_now)
