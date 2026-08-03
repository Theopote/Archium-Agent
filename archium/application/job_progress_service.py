"""Unified job progress across WorkflowRun and ArtifactJob."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.background_job import BackgroundJobStatus
from archium.domain.enums import ArtifactJobStatus, WorkflowStatus
from archium.domain.job_progress import JobKind, JobProgressView
from archium.infrastructure.database.repositories import (
    ArtifactJobRepository,
    BackgroundJobRepository,
    WorkflowRunRepository,
)


def _workflow_progress_pct(status: WorkflowStatus, state: dict) -> int | None:
    if status == WorkflowStatus.COMPLETED:
        return 100
    if status in {WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}:
        return None
    if status == WorkflowStatus.AWAITING_REVIEW:
        return 70
    timeline = state.get("process_timeline") or []
    if isinstance(timeline, list) and timeline:
        return min(90, 15 + len(timeline) * 12)
    step = str(state.get("current_step") or "").strip()
    if step:
        return 40
    if status == WorkflowStatus.RUNNING:
        return 20
    return None


def _artifact_progress_pct(status: ArtifactJobStatus) -> int | None:
    mapping = {
        ArtifactJobStatus.PLANNED: 0,
        ArtifactJobStatus.READY: 10,
        ArtifactJobStatus.RUNNING: 55,
        ArtifactJobStatus.COMPLETED: 100,
        ArtifactJobStatus.FAILED: None,
    }
    return mapping.get(status)


def _workflow_label(state: dict, status: WorkflowStatus) -> str:
    kind = str(state.get("workflow_kind") or state.get("orchestration_kind") or "").strip()
    if kind == "planning":
        base = "规划工作流"
    elif kind == "orchestration":
        base = "编排工作流"
    elif kind == "visual":
        base = "视觉工作流"
    elif state.get("presentation_id") or "storyline" in state:
        base = "汇报生成"
    else:
        base = "工作流"
    step = str(state.get("current_step") or "").strip()
    if step:
        return f"{base} · {step}"
    if status == WorkflowStatus.AWAITING_REVIEW:
        return f"{base} · 等待确认"
    return base


class JobProgressService:
    """Read-model over existing job stores for partner progress UI."""

    def __init__(self, session: Session) -> None:
        self._workflows = WorkflowRunRepository(session)
        self._artifacts = ArtifactJobRepository(session)
        self._background = BackgroundJobRepository(session)

    def list_for_project(
        self,
        project_id: UUID,
        *,
        limit: int = 12,
        active_only: bool = False,
    ) -> list[JobProgressView]:
        rows: list[JobProgressView] = []
        for run in self._workflows.list_by_project(project_id)[:24]:
            if active_only and run.status in {
                WorkflowStatus.COMPLETED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            }:
                continue
            state = dict(run.state or {})
            message = ""
            errors = list(run.errors or [])
            if errors:
                message = str(errors[-1])[:200]
            elif state.get("awaiting_review"):
                message = "等待人工确认"
            rows.append(
                JobProgressView(
                    job_id=run.id,
                    project_id=project_id,
                    kind=JobKind.WORKFLOW,
                    label=_workflow_label(state, run.status),
                    status=run.status.value,
                    progress_pct=_workflow_progress_pct(run.status, state),
                    message=message,
                    updated_at=run.updated_at,
                    detail={
                        "presentation_id": (
                            str(run.presentation_id) if run.presentation_id else ""
                        )
                    },
                )
            )

        try:
            artifacts = self._artifacts.list_by_project(project_id, limit=24)
        except Exception:
            artifacts = []
        for job in artifacts:
            if active_only and job.status in {
                ArtifactJobStatus.COMPLETED,
                ArtifactJobStatus.FAILED,
            }:
                continue
            title = (job.deliverable_title or job.title or job.deliverable_id).strip()
            rows.append(
                JobProgressView(
                    job_id=job.id,
                    project_id=project_id,
                    kind=JobKind.ARTIFACT,
                    label=f"成果 · {title}" if title else "成果任务",
                    status=job.status.value,
                    progress_pct=_artifact_progress_pct(job.status),
                    message=(job.message or job.error_message or "")[:200],
                    updated_at=job.updated_at,
                    detail={"deliverable_id": job.deliverable_id},
                )
            )

        try:
            background = self._background.list_for_project(project_id, limit=24)
        except Exception:
            background = []
        for bg_job in background:
            if active_only and bg_job.status in {
                BackgroundJobStatus.COMPLETED,
                BackgroundJobStatus.FAILED,
                BackgroundJobStatus.CANCELLED,
            }:
                continue
            rows.append(
                JobProgressView(
                    job_id=bg_job.id,
                    project_id=project_id,
                    kind=JobKind.BACKGROUND,
                    label=bg_job.label or f"后台 · {bg_job.kind.value}",
                    status=bg_job.status.value,
                    progress_pct=bg_job.progress_pct,
                    message=(bg_job.message or bg_job.error_message or "")[:200],
                    updated_at=bg_job.updated_at,
                    detail={"kind": bg_job.kind.value},
                )
            )

        rows.sort(
            key=lambda item: item.updated_at.timestamp() if item.updated_at else 0.0,
            reverse=True,
        )
        return rows[:limit]

    def get(self, job_id: UUID) -> JobProgressView | None:
        """Resolve a single job across workflow / artifact / background stores."""
        run = self._workflows.get_by_id(job_id)
        if run is not None:
            state = dict(run.state or {})
            message = ""
            errors = list(run.errors or [])
            if errors:
                message = str(errors[-1])[:200]
            elif state.get("awaiting_review"):
                message = "等待人工确认"
            return JobProgressView(
                job_id=run.id,
                project_id=run.project_id,
                kind=JobKind.WORKFLOW,
                label=_workflow_label(state, run.status),
                status=run.status.value,
                progress_pct=_workflow_progress_pct(run.status, state),
                message=message,
                updated_at=run.updated_at,
                detail={
                    "presentation_id": (
                        str(run.presentation_id) if run.presentation_id else ""
                    )
                },
            )
        try:
            artifact = self._artifacts.get(job_id)
        except Exception:
            artifact = None
        if artifact is not None:
            title = (artifact.deliverable_title or artifact.title or artifact.deliverable_id).strip()
            return JobProgressView(
                job_id=artifact.id,
                project_id=artifact.project_id,
                kind=JobKind.ARTIFACT,
                label=f"成果 · {title}" if title else "成果任务",
                status=artifact.status.value,
                progress_pct=_artifact_progress_pct(artifact.status),
                message=(artifact.message or artifact.error_message or "")[:200],
                updated_at=artifact.updated_at,
                detail={"deliverable_id": artifact.deliverable_id},
            )
        bg_job = self._background.get_by_id(job_id)
        if bg_job is None:
            return None
        return JobProgressView(
            job_id=bg_job.id,
            project_id=bg_job.project_id,
            kind=JobKind.BACKGROUND,
            label=bg_job.label or f"后台 · {bg_job.kind.value}",
            status=bg_job.status.value,
            progress_pct=bg_job.progress_pct,
            message=(bg_job.message or bg_job.error_message or "")[:200],
            updated_at=bg_job.updated_at,
            detail={
                "kind": bg_job.kind.value,
                "idempotency_key": bg_job.idempotency_key or "",
                "cancel_requested": bg_job.cancel_requested,
            },
        )
