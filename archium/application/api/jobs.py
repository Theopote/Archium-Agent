"""/jobs — durable long-running work with progress, cancel, and idempotency.

Scope: BackgroundJob only. Sync Render/Delivery exports and LangGraph
WorkflowRun paths are separate (see APP-029 contract). Idempotency means
the same (project_id, idempotency_key) returns the same job row — not that
downstream artifacts are never regenerated.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.background_job_service import BackgroundJobService
from archium.application.job_progress_service import JobProgressService
from archium.application.operation_view_service import OperationViewService
from archium.domain.background_job import BackgroundJob, BackgroundJobKind, BackgroundJobStatus
from archium.domain.job_progress import JobProgressView
from archium.domain.operation_view import OperationView
from archium.exceptions import ValidationError


class JobsApi:
    """Durable job boundary for UI and workers (progress / cancel / refresh)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._jobs = BackgroundJobService(session)
        self._progress = JobProgressService(session)
        self._operations = OperationViewService(session)

    def create(
        self,
        project_id: UUID,
        kind: BackgroundJobKind | str,
        *,
        label: str = "",
        payload: dict[str, Any] | None = None,
        message: str = "queued",
        idempotency_key: str | None = None,
    ) -> BackgroundJob:
        if isinstance(kind, str):
            try:
                kind = BackgroundJobKind(kind)
            except ValueError as exc:
                raise ValidationError(f"未知任务类型: {kind}") from exc
        return self._jobs.enqueue(
            project_id,
            kind,
            label=label,
            payload=payload,
            message=message,
            idempotency_key=idempotency_key,
        )

    def get(self, job_id: UUID) -> BackgroundJob | None:
        return self._jobs.get(job_id)

    def get_progress(self, job_id: UUID) -> JobProgressView | None:
        return self._progress.get(job_id)

    def list_for_project(
        self,
        project_id: UUID,
        *,
        limit: int = 24,
        status: BackgroundJobStatus | None = None,
        active_only: bool = False,
    ) -> list[JobProgressView]:
        if status is not None and not active_only:
            jobs = self._jobs.list_for_project(project_id, limit=limit, status=status)
            return [
                view
                for job in jobs
                if (view := self._progress.get(job.id)) is not None
            ]
        return self._progress.list_for_project(
            project_id,
            limit=limit,
            active_only=active_only,
        )

    def cancel(self, job_id: UUID, *, message: str = "cancelled") -> BackgroundJob | None:
        return self._jobs.cancel(job_id, message=message)

    def list_active(self, project_id: UUID, *, limit: int = 12) -> list[JobProgressView]:
        """Jobs still recoverable after page refresh."""
        return self._progress.list_for_project(project_id, limit=limit, active_only=True)

    def list_operations(
        self,
        project_id: UUID,
        *,
        limit: int = 24,
        active_only: bool = False,
        include_workflows: bool = True,
    ) -> list[OperationView]:
        """Unified user-facing operations (jobs + optional WorkflowRun)."""
        return self._operations.list_for_project(
            project_id,
            limit=limit,
            active_only=active_only,
            include_workflows=include_workflows,
        )
