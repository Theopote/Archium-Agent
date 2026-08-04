"""User-facing operation status — unifies Job / WorkflowRun / sync labels."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class OperationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_USER = "awaiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationView(DomainModel):
    """Architect-facing execution row (read model; not a second store).

    ``cancellable`` / ``retryable`` mean a product action is **already wired**
    (e.g. ``JobsApi.cancel`` for BackgroundJob). They are not a wishlist —
    OperationView unifies **reads**; durable actions stay on ``JobsApi`` until
    Job/Workflow dual-track converges (APP-029).
    """

    operation_id: UUID
    project_id: UUID
    operation_type: str = ""
    label: str = ""
    status: OperationStatus = OperationStatus.QUEUED
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    message: str = ""
    cancellable: bool = False
    retryable: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_activity_at: datetime | None = None
    source_kind: Literal["job", "workflow", "sync"] = "job"
    detail: dict[str, object] = Field(default_factory=dict)

    def display_line(self) -> str:
        pct = "—" if self.progress is None else f"{int(round(self.progress * 100))}%"
        return f"{self.label or self.operation_type} · {self.status.value} · {pct}"
