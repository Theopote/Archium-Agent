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
    artifact_kind: str = Field(default="pptx", max_length=50)
    derived_from_artifact_ids: list[UUID] = Field(default_factory=list)
    generator_version: str = Field(default="archium-unknown", max_length=100)
    font_manifest_hash: str | None = Field(default=None, max_length=128)
    theme_version: str | None = Field(default=None, max_length=100)
    export_policy: str | None = Field(default=None, max_length=100)
    format: str = Field(min_length=1, max_length=40)
    file_uri: str = Field(min_length=1, max_length=2000)
    file_hash: str = Field(default="", max_length=128)
    qa_status: str = Field(default="unknown", max_length=40)
    round_trip_report_json: dict[str, object] | None = None
    exported_at: datetime = Field(default_factory=utc_now)
