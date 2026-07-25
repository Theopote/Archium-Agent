"""Durable background job enqueue / claim / complete."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.background_job import (
    BackgroundJob,
    BackgroundJobKind,
    BackgroundJobStatus,
)
from archium.infrastructure.database.repositories import BackgroundJobRepository


class BackgroundJobService:
    """Process-agnostic job queue API (Streamlit runner remains a separate adapter)."""

    def __init__(self, session: Session) -> None:
        self._repo = BackgroundJobRepository(session)

    def enqueue(
        self,
        project_id: UUID,
        kind: BackgroundJobKind,
        *,
        label: str = "",
        payload: dict[str, Any] | None = None,
        message: str = "queued",
    ) -> BackgroundJob:
        job = BackgroundJob(
            project_id=project_id,
            kind=kind,
            status=BackgroundJobStatus.QUEUED,
            label=(label or kind.value)[:300],
            message=message[:500],
            payload=dict(payload or {}),
        )
        return self._repo.create(job)

    def claim_next(self) -> BackgroundJob | None:
        return self._repo.claim_next()

    def set_progress(self, job_id: UUID, pct: int, *, message: str = "") -> BackgroundJob | None:
        job = self._repo.get_by_id(job_id)
        if job is None:
            return None
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
        job.mark_completed(result=result, message=message)
        return self._repo.update(job)

    def fail(self, job_id: UUID, error_message: str) -> BackgroundJob | None:
        job = self._repo.get_by_id(job_id)
        if job is None:
            return None
        job.mark_failed(error_message[:800])
        return self._repo.update(job)

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
