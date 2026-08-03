"""Map durable jobs (and later WorkflowRun) into OperationView for UI."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.application.job_progress_service import JobProgressService
from archium.domain.job_progress import JobKind, JobProgressView
from archium.domain.operation_view import OperationStatus, OperationView
from archium.domain.workflow import WorkflowRun
from archium.infrastructure.database.repositories import WorkflowRunRepository


_STATUS_MAP = {
    "queued": OperationStatus.QUEUED,
    "running": OperationStatus.RUNNING,
    "awaiting_review": OperationStatus.AWAITING_USER,
    "completed": OperationStatus.COMPLETED,
    "failed": OperationStatus.FAILED,
    "cancelled": OperationStatus.CANCELLED,
}


def operation_from_job_progress(view: JobProgressView) -> OperationView:
    status = _STATUS_MAP.get(str(view.status).lower(), OperationStatus.RUNNING)
    pct = view.progress_pct
    progress = None if pct is None else max(0.0, min(1.0, pct / 100.0))
    terminal = status in {
        OperationStatus.COMPLETED,
        OperationStatus.FAILED,
        OperationStatus.CANCELLED,
    }
    return OperationView(
        operation_id=view.job_id,
        project_id=view.project_id,
        operation_type=view.kind.value,
        label=view.label,
        status=status,
        progress=progress,
        message=view.message,
        cancellable=not terminal and view.kind == JobKind.BACKGROUND,
        retryable=status == OperationStatus.FAILED,
        started_at=None,
        completed_at=view.updated_at if terminal else None,
        source_kind="job",
        detail=dict(view.detail),
    )


def operation_from_workflow_run(run: WorkflowRun) -> OperationView:
    raw = str(run.status.value if hasattr(run.status, "value") else run.status).lower()
    status = _STATUS_MAP.get(raw, OperationStatus.RUNNING)
    step = ""
    if isinstance(run.state, dict):
        step = str(run.state.get("current_step") or run.state.get("review_gate") or "")
    kind = ""
    if isinstance(run.state, dict):
        kind = str(run.state.get("workflow_kind") or "workflow")
    terminal = status in {
        OperationStatus.COMPLETED,
        OperationStatus.FAILED,
        OperationStatus.CANCELLED,
    }
    return OperationView(
        operation_id=run.id,
        project_id=run.project_id,
        operation_type=kind or "workflow",
        label=step or kind or "工作流",
        status=status,
        progress=None,
        message=step,
        cancellable=False,
        retryable=status == OperationStatus.FAILED,
        started_at=run.created_at,
        completed_at=run.updated_at if terminal else None,
        source_kind="workflow",
        detail={"errors": list(run.errors or [])},
    )


class OperationViewService:
    """Product-facing operation list; persistence stays dual-track underneath."""

    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._progress = JobProgressService(session)
        self._runs = WorkflowRunRepository(session)

    def list_for_project(
        self,
        project_id: UUID,
        *,
        limit: int = 24,
        active_only: bool = False,
        include_workflows: bool = True,
    ) -> list[OperationView]:
        jobs = [
            operation_from_job_progress(view)
            for view in self._progress.list_for_project(
                project_id, limit=limit, active_only=active_only
            )
        ]
        if not include_workflows:
            return jobs[:limit]
        runs = self._runs.list_by_project(project_id)
        workflow_ops = [operation_from_workflow_run(run) for run in runs]
        if active_only:
            workflow_ops = [
                item
                for item in workflow_ops
                if item.status
                in {
                    OperationStatus.QUEUED,
                    OperationStatus.RUNNING,
                    OperationStatus.AWAITING_USER,
                }
            ]
        merged = jobs + workflow_ops

        def _sort_key(item: OperationView) -> tuple[float, str]:
            stamp = item.completed_at or item.started_at
            epoch = stamp.timestamp() if stamp is not None else 0.0
            return (epoch, str(item.operation_id))

        merged.sort(key=_sort_key, reverse=True)
        return merged[:limit]
