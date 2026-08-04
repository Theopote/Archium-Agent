"""OperationView mapping and list ordering."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from archium.application.operation_view_service import (
    operation_from_job_progress,
    operation_from_workflow_run,
)
from archium.domain.enums import WorkflowStatus
from archium.domain.job_progress import JobKind, JobProgressView
from archium.domain.operation_view import OperationStatus
from archium.domain.workflow import WorkflowRun


def test_operation_from_job_progress_uses_real_timestamps() -> None:
    created = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    updated = datetime(2026, 8, 1, 11, 0, tzinfo=UTC)
    view = JobProgressView(
        job_id=uuid4(),
        project_id=uuid4(),
        kind=JobKind.BACKGROUND,
        label="解析",
        status="queued",
        progress_pct=0,
        created_at=created,
        started_at=None,
        updated_at=updated,
        completed_at=None,
    )
    op = operation_from_job_progress(view)
    assert op.status == OperationStatus.QUEUED
    assert op.started_at == created
    assert op.completed_at is None
    assert op.last_activity_at == updated
    assert op.cancellable is True
    assert op.retryable is False


def test_operation_from_job_progress_terminal_keeps_completed_at() -> None:
    created = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    started = datetime(2026, 8, 1, 10, 5, tzinfo=UTC)
    completed = datetime(2026, 8, 1, 10, 30, tzinfo=UTC)
    view = JobProgressView(
        job_id=uuid4(),
        project_id=uuid4(),
        kind=JobKind.BACKGROUND,
        label="解析",
        status="completed",
        progress_pct=100,
        created_at=created,
        started_at=started,
        updated_at=completed,
        completed_at=completed,
    )
    op = operation_from_job_progress(view)
    assert op.started_at == started
    assert op.completed_at == completed
    assert op.last_activity_at == completed
    assert op.cancellable is False
    assert op.retryable is False


def test_failed_job_not_retryable_until_api_exists() -> None:
    view = JobProgressView(
        job_id=uuid4(),
        project_id=uuid4(),
        kind=JobKind.BACKGROUND,
        label="失败任务",
        status="failed",
        progress_pct=None,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        updated_at=datetime(2026, 8, 1, tzinfo=UTC),
        completed_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    op = operation_from_job_progress(view)
    assert op.status == OperationStatus.FAILED
    assert op.cancellable is False
    assert op.retryable is False


def test_workflow_operation_has_no_wired_actions() -> None:
    run = WorkflowRun(
        id=uuid4(),
        project_id=uuid4(),
        status=WorkflowStatus.FAILED,
        state={"workflow_kind": "planning"},
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        updated_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    op = operation_from_workflow_run(run)
    assert op.source_kind == "workflow"
    assert op.cancellable is False
    assert op.retryable is False


def test_artifact_job_not_cancellable_via_jobs_api() -> None:
    view = JobProgressView(
        job_id=uuid4(),
        project_id=uuid4(),
        kind=JobKind.ARTIFACT,
        label="成果",
        status="running",
        progress_pct=50,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        updated_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    op = operation_from_job_progress(view)
    assert op.cancellable is False
    assert op.retryable is False


def test_merged_operations_sort_by_last_activity_not_uuid() -> None:
    project_id = uuid4()
    older = datetime(2026, 7, 1, tzinfo=UTC)
    newer = older + timedelta(days=10)
    stale_workflow = operation_from_workflow_run(
        WorkflowRun(
            id=uuid4(),
            project_id=project_id,
            status=WorkflowStatus.RUNNING,
            state={"workflow_kind": "planning"},
            created_at=older,
            updated_at=older,
        )
    )
    active_job = operation_from_job_progress(
        JobProgressView(
            job_id=uuid4(),
            project_id=project_id,
            kind=JobKind.BACKGROUND,
            label="新任务",
            status="running",
            progress_pct=20,
            created_at=newer,
            started_at=newer,
            updated_at=newer,
        )
    )
    # Simulate list_for_project sort key.
    merged = [stale_workflow, active_job]
    merged.sort(
        key=lambda item: (
            (item.last_activity_at or item.completed_at or item.started_at).timestamp()
            if (item.last_activity_at or item.completed_at or item.started_at)
            else 0.0,
            str(item.operation_id),
        ),
        reverse=True,
    )
    assert merged[0].operation_id == active_job.operation_id
    assert merged[0].last_activity_at == newer
