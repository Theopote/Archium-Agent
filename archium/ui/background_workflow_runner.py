"""Background LangGraph execution for Streamlit long-running workflows."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from archium.application.presentation_models import PresentationRequest
from archium.application.workflow_models import WorkflowRunResult
from archium.config.settings import Settings
from archium.domain.enums import WorkflowStatus
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import WorkflowRunRepository
from archium.infrastructure.database.session import get_session
from archium.infrastructure.llm.factory import create_llm_provider
from archium.ui.workflow_resources import get_workflow_checkpointer_manager


class BackgroundJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BackgroundWorkflowJob:
    """In-process background workflow job tracked for Streamlit polling."""

    job_id: str
    project_id: UUID
    workflow_run_id: UUID | None = None
    status: BackgroundJobStatus = BackgroundJobStatus.PENDING
    error: str | None = None
    result: WorkflowRunResult | None = None
    kind: str = "presentation"
    _thread: threading.Thread | None = field(default=None, repr=False)


_REGISTRY: dict[str, BackgroundWorkflowJob] = {}
_LOCK = threading.Lock()


def _resolve_settings(settings: Settings | None) -> Settings:
    if settings is not None:
        return settings
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx() is not None:
            from archium.ui.llm_settings import get_ui_effective_settings

            return get_ui_effective_settings()
    except Exception:
        pass
    from archium.config.llm_config import get_effective_settings

    return get_effective_settings()


def _create_presentation_service(session, llm, settings: Settings):
    from archium.application.presentation_workflow_service import PresentationWorkflowService

    return PresentationWorkflowService(
        session,
        llm,
        settings=settings,
        checkpointer_manager=get_workflow_checkpointer_manager(settings),
    )


def _set_job_status(job: BackgroundWorkflowJob, status: BackgroundJobStatus) -> None:
    job.status = status


def _run_presentation_job(
    job: BackgroundWorkflowJob,
    *,
    request: PresentationRequest,
    settings: Settings,
    export_kwargs: dict[str, Any],
) -> None:
    _set_job_status(job, BackgroundJobStatus.RUNNING)
    try:
        with get_session() as session:
            llm = create_llm_provider(settings)
            service = _create_presentation_service(session, llm, settings)
            try:
                workflow_run = service.prepare_run(job.project_id, request, **export_kwargs)
                job.workflow_run_id = workflow_run.id
                result = service.execute_prepared(workflow_run.id)
                job.result = result
                if result.awaiting_review:
                    _set_job_status(job, BackgroundJobStatus.AWAITING_REVIEW)
                elif result.succeeded:
                    _set_job_status(job, BackgroundJobStatus.COMPLETED)
                else:
                    _set_job_status(job, BackgroundJobStatus.FAILED)
                    job.error = "; ".join(result.errors) or "工作流完成但存在错误"
            finally:
                service.close()
    except WorkflowError as exc:
        job.error = str(exc)
        _set_job_status(job, BackgroundJobStatus.FAILED)
    except Exception as exc:
        job.error = str(exc)
        _set_job_status(job, BackgroundJobStatus.FAILED)


def _run_continue_job(job: BackgroundWorkflowJob, *, settings: Settings) -> None:
    if job.workflow_run_id is None:
        job.error = "缺少 workflow_run_id"
        _set_job_status(job, BackgroundJobStatus.FAILED)
        return
    _set_job_status(job, BackgroundJobStatus.RUNNING)
    try:
        with get_session() as session:
            llm = create_llm_provider(settings)
            service = _create_presentation_service(session, llm, settings)
            try:
                result = service.continue_after_review(job.workflow_run_id)
                job.result = result
                if result.awaiting_review:
                    _set_job_status(job, BackgroundJobStatus.AWAITING_REVIEW)
                elif result.succeeded:
                    _set_job_status(job, BackgroundJobStatus.COMPLETED)
                else:
                    _set_job_status(job, BackgroundJobStatus.FAILED)
                    job.error = "; ".join(result.errors) or "工作流继续执行时出现错误"
            finally:
                service.close()
    except WorkflowError as exc:
        job.error = str(exc)
        _set_job_status(job, BackgroundJobStatus.FAILED)
    except Exception as exc:
        job.error = str(exc)
        _set_job_status(job, BackgroundJobStatus.FAILED)


def register_job(job: BackgroundWorkflowJob) -> None:
    with _LOCK:
        _REGISTRY[job.job_id] = job


def get_job(job_id: str) -> BackgroundWorkflowJob | None:
    with _LOCK:
        return _REGISTRY.get(job_id)


def start_background_thread(job: BackgroundWorkflowJob, target: Callable[[], None]) -> None:
    thread = threading.Thread(target=target, name=f"archium-wf-{job.job_id[:8]}", daemon=True)
    job._thread = thread
    register_job(job)
    thread.start()


def submit_presentation_workflow(
    project_id: UUID,
    request: PresentationRequest,
    *,
    settings: Settings | None = None,
    **export_kwargs: Any,
) -> BackgroundWorkflowJob:
    """Start a presentation workflow in a daemon background thread."""
    resolved = _resolve_settings(settings)
    job = BackgroundWorkflowJob(job_id=str(uuid4()), project_id=project_id)
    start_background_thread(
        job,
        lambda: _run_presentation_job(
            job,
            request=request,
            settings=resolved,
            export_kwargs=export_kwargs,
        ),
    )
    return job


def submit_continue_after_review(
    project_id: UUID,
    workflow_run_id: UUID,
    *,
    settings: Settings | None = None,
) -> BackgroundWorkflowJob:
    """Continue a paused presentation workflow in the background."""
    resolved = _resolve_settings(settings)
    job = BackgroundWorkflowJob(
        job_id=str(uuid4()),
        project_id=project_id,
        workflow_run_id=workflow_run_id,
    )
    start_background_thread(
        job,
        lambda: _run_continue_job(job, settings=resolved),
    )
    return job


def find_running_workflow_run_id(project_id: UUID) -> UUID | None:
    """Return the newest in-flight workflow run for a project (browser refresh recovery)."""
    with get_session() as session:
        runs = WorkflowRunRepository(session).list_by_project(project_id)
    for run in runs:
        if run.status == WorkflowStatus.RUNNING:
            return run.id
    return None


def load_workflow_result(workflow_run_id: UUID, *, settings: Settings | None = None) -> WorkflowRunResult:
    """Load a WorkflowRunResult from persisted DB state."""
    resolved = _resolve_settings(settings)
    with get_session() as session:
        llm = create_llm_provider(resolved)
        service = _create_presentation_service(session, llm, resolved)
        try:
            return service.result_from_run(workflow_run_id)
        finally:
            service.close()


def background_workflows_enabled(settings: Settings | None = None) -> bool:
    resolved = _resolve_settings(settings)
    return resolved.streamlit_background_workflows_enabled
