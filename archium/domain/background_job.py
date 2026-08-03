"""Durable background job — process-agnostic queue row (not Streamlit-only)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel, utc_now


class BackgroundJobKind(StrEnum):
    DOCUMENT_ANALYZE = "document_analyze"
    WORKFLOW = "workflow"
    ARTIFACT = "artifact"
    GENERIC = "generic"


class BackgroundJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackgroundJob(IdentifiedModel, TimestampedModel):
    """One queued unit of long-running work."""

    project_id: UUID
    kind: BackgroundJobKind = BackgroundJobKind.GENERIC
    status: BackgroundJobStatus = BackgroundJobStatus.QUEUED
    label: str = Field(default="", max_length=300)
    progress_pct: int = Field(default=0, ge=0, le=100)
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    attempts: int = Field(default=0, ge=0)
    idempotency_key: str | None = Field(default=None, max_length=200)
    cancel_requested: bool = False

    def mark_running(self, *, message: str = "") -> None:
        self.status = BackgroundJobStatus.RUNNING
        self.started_at = utc_now()
        self.attempts += 1
        if message:
            self.message = message
        self.touch()

    def set_progress(self, pct: int, *, message: str = "") -> None:
        self.progress_pct = max(0, min(100, int(pct)))
        if message:
            self.message = message
        self.touch()

    def request_cancel(self, *, message: str = "cancel requested") -> None:
        self.cancel_requested = True
        if message:
            self.message = message[:500]
        self.touch()

    def mark_cancelled(self, *, message: str = "cancelled") -> None:
        self.status = BackgroundJobStatus.CANCELLED
        self.cancel_requested = True
        self.message = (message or "cancelled")[:500]
        self.completed_at = utc_now()
        self.touch()

    def mark_completed(self, *, result: dict[str, Any] | None = None, message: str = "") -> None:
        self.status = BackgroundJobStatus.COMPLETED
        self.progress_pct = 100
        self.result = dict(result or {})
        if message:
            self.message = message
        self.error_message = None
        self.completed_at = utc_now()
        self.touch()

    def mark_failed(self, error_message: str) -> None:
        self.status = BackgroundJobStatus.FAILED
        self.error_message = error_message
        self.completed_at = utc_now()
        self.touch()
