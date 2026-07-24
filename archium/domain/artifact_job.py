"""Artifact job — persisted generation lifecycle for non-presentation deliverables."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel, utc_now
from archium.domain.enums import ArtifactJobStatus, DeliverableType


class ArtifactJob(IdentifiedModel, TimestampedModel):
    """One planned or executed non-presentation artifact generation."""

    project_id: UUID
    mission_id: UUID
    deliverable_id: str = Field(min_length=1, max_length=100)
    deliverable_title: str = Field(default="", max_length=500)
    deliverable_type: DeliverableType = DeliverableType.OTHER
    request_kind: str = Field(default="other", max_length=50)
    status: ArtifactJobStatus = ArtifactJobStatus.PLANNED
    message: str = ""
    warnings: list[str] = Field(default_factory=list)
    plan_json: dict[str, Any] = Field(default_factory=dict)
    title: str = Field(default="", max_length=500)
    payload_json: dict[str, Any] = Field(default_factory=dict)
    markdown: str = ""
    json_path: str | None = Field(default=None, max_length=2000)
    markdown_path: str | None = Field(default=None, max_length=2000)
    docx_path: str | None = Field(default=None, max_length=2000)
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def mark_ready(self) -> None:
        self.status = ArtifactJobStatus.READY
        self.touch()

    def mark_running(self) -> None:
        self.status = ArtifactJobStatus.RUNNING
        self.started_at = utc_now()
        self.touch()

    def mark_completed(
        self,
        *,
        title: str,
        payload: dict[str, Any],
        markdown: str,
        json_path: str | None = None,
        markdown_path: str | None = None,
        docx_path: str | None = None,
    ) -> None:
        self.status = ArtifactJobStatus.COMPLETED
        self.title = title
        self.payload_json = payload
        self.markdown = markdown
        self.json_path = json_path
        self.markdown_path = markdown_path
        self.docx_path = docx_path
        self.error_message = None
        self.completed_at = utc_now()
        self.touch()

    def mark_failed(self, error_message: str) -> None:
        self.status = ArtifactJobStatus.FAILED
        self.error_message = error_message
        self.completed_at = utc_now()
        self.touch()
