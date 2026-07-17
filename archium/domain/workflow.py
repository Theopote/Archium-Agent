"""Workflow run domain model."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.enums import WorkflowStatus


class WorkflowRun(IdentifiedModel, TimestampedModel):
    """Persisted execution record for a multi-step presentation workflow."""

    project_id: UUID
    presentation_id: UUID
    status: WorkflowStatus = WorkflowStatus.RUNNING
    state: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)

    def touch(self) -> None:
        TimestampedModel.touch(self)
