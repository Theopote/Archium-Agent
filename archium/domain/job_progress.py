"""Unified job progress view — WorkflowRun + ArtifactJob for partner UI."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class JobKind(StrEnum):
    WORKFLOW = "workflow"
    ARTIFACT = "artifact"
    BACKGROUND = "background"


class JobProgressView(DomainModel):
    """Architect-facing progress row (not a second job store)."""

    job_id: UUID
    project_id: UUID
    kind: JobKind
    label: str = ""
    status: str = ""
    progress_pct: int | None = Field(default=None, ge=0, le=100)
    message: str = ""
    created_at: datetime | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    detail: dict[str, object] = Field(default_factory=dict)

    def display_line(self) -> str:
        pct = f"{self.progress_pct}%" if self.progress_pct is not None else "—"
        return f"{self.label} · {self.status} · {pct}"

    def last_activity_at(self) -> datetime | None:
        """Best stamp for recency sorting (update > complete > start > create)."""
        return self.updated_at or self.completed_at or self.started_at or self.created_at
