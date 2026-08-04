"""Durable background job enqueue / claim / complete / cancel."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from archium.application.unit_of_work import SessionLike, session_of
from archium.domain.background_job import (
    BackgroundJob,
    BackgroundJobKind,
    BackgroundJobStatus,
)
from archium.infrastructure.database.repositories import BackgroundJobRepository


class BackgroundJobService:
    """Process-agnostic job queue API (Streamlit runner remains a separate adapter)."""

    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._repo = BackgroundJobRepository(session)

    def enqueue(
        self,
        project_id: UUID,
        kind: BackgroundJobKind,
        *,
        label: str = "",
        payload: dict[str, Any] | None = None,
        message: str = "queued",
        idempotency_key: str | None = None,
    ) -> BackgroundJob:
        key = (idempotency_key or "").strip() or None
        if key is not None:
            existing = self._repo.get_by_idempotency_key(project_id, key)
            if existing is not None:
                return existing
        job = BackgroundJob(
            project_id=project_id,
            kind=kind,
            status=BackgroundJobStatus.QUEUED,
            label=(label or kind.value)[:300],
            message=message[:500],
            payload=dict(payload or {}),
            idempotency_key=key,
        )
        return self._repo.create(job)

    def claim_next(self) -> BackgroundJob | None:
        return self._repo.claim_next()

    def set_progress(self, job_id: UUID, pct: int, *, message: str = "") -> BackgroundJob | None:
        job = self._repo.get_by_id(job_id)
        if job is None:
            return None
        if job.cancel_requested or job.status == BackgroundJobStatus.CANCELLED:
            return job
        job.set_progress(pct, message=message)
        return self._repo.update(job)

    def complete(
        self,
        job_id: UUID,
        *,
        result: dict[str, Any] | None = None,
        message: str = "completed",
    ) -> BackgroundJob | None:
        job = self._repo.get_by_id(job_id)
        if job is None:
            return None
        if job.cancel_requested or job.status == BackgroundJobStatus.CANCELLED:
            if job.status != BackgroundJobStatus.CANCELLED:
                job.mark_cancelled(message=job.message or "cancelled")
                return self._repo.update(job)
            return job
        job.mark_completed(result=result, message=message)
        return self._repo.update(job)

    def fail(self, job_id: UUID, error_message: str) -> BackgroundJob | None:
        job = self._repo.get_by_id(job_id)
        if job is None:
            return None
        if job.status == BackgroundJobStatus.CANCELLED:
            return job
        job.mark_failed(error_message[:800])
        return self._repo.update(job)

    def cancel(self, job_id: UUID, *, message: str = "cancelled") -> BackgroundJob | None:
        """Cancel a job. Queued jobs finish immediately; running jobs cooperate."""
        job = self._repo.get_by_id(job_id)
        if job is None:
            return None
        if job.status in {
            BackgroundJobStatus.COMPLETED,
            BackgroundJobStatus.FAILED,
            BackgroundJobStatus.CANCELLED,
        }:
            return job
        # Queued, or worker acknowledging a prior cancel request → terminal CANCELLED.
        if job.status == BackgroundJobStatus.QUEUED or job.cancel_requested:
            job.mark_cancelled(message=message)
            return self._repo.update(job)
        job.request_cancel(message=message or "cancel requested")
        return self._repo.update(job)

    def is_cancel_requested(self, job_id: UUID) -> bool:
        job = self._repo.get_by_id(job_id)
        if job is None:
            return False
        return bool(job.cancel_requested or job.status == BackgroundJobStatus.CANCELLED)

    def list_for_project(
        self,
        project_id: UUID,
        *,
        limit: int = 24,
        status: BackgroundJobStatus | None = None,
    ) -> list[BackgroundJob]:
        return self._repo.list_for_project(project_id, limit=limit, status=status)

    def get(self, job_id: UUID) -> BackgroundJob | None:
        return self._repo.get_by_id(job_id)
