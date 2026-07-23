"""Background LangGraph execution for Streamlit long-running workflows."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.application.planning_workflow_service import (
    PlanningWorkflowResult,
    PlanningWorkflowService,
)
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.application.slide_recovery_workflow_service import (
    SlideRecoveryWorkflowRequest,
    SlideRecoveryWorkflowResult,
    SlideRecoveryWorkflowService,
)
from archium.application.visual.visual_workflow_service import (
    VisualWorkflowResult,
    VisualWorkflowService,
)
from archium.application.workflow_models import WorkflowRunResult
from archium.config.settings import Settings
from archium.domain.enums import WorkflowStatus
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import WorkflowRunRepository
from archium.infrastructure.database.session import get_session
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.llm.factory import create_llm_provider
from archium.ui.workflow_resources import get_workflow_checkpointer_manager


class BackgroundJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"


class PlanningJobAction(StrEnum):
    START = "start"
    CONTINUE_MISSION_CORRECTION = "continue_mission_correction"
    APPROVE_MISSION = "approve_mission"
    CONTINUE_CLARIFICATION = "continue_clarification"
    START_PRESENTATION = "start_presentation"


class VisualJobAction(StrEnum):
    RUN = "run"
    CONTINUE_LAYOUT_REVIEW = "continue_layout_review"


class SlideRecoveryJobAction(StrEnum):
    RUN = "run"
    CONTINUE_REVIEW = "continue_review"


@dataclass
class BackgroundWorkflowJob:
    """In-process background workflow job tracked for Streamlit polling."""

    job_id: str
    project_id: UUID
    workflow_run_id: UUID | None = None
    presentation_id: UUID | None = None
    status: BackgroundJobStatus = BackgroundJobStatus.PENDING
    error: str | None = None
    result: Any | None = None
    kind: str = "presentation"
    action: str | None = None
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
    except (ImportError, RuntimeError):
        # Streamlit not available or not in Streamlit context
        pass
    from archium.config.llm_config import get_effective_settings

    return get_effective_settings()


def _create_presentation_service(
    session: Session, llm: LLMProvider, settings: Settings
) -> PresentationWorkflowService:
    return PresentationWorkflowService(
        session,
        llm,
        settings=settings,
        checkpointer_manager=get_workflow_checkpointer_manager(settings),
    )


def _create_planning_service(session: Session, settings: Settings) -> PlanningWorkflowService:
    llm = create_llm_provider(settings)
    return PlanningWorkflowService(
        session,
        llm,
        settings=settings,
        checkpointer_manager=get_workflow_checkpointer_manager(settings),
    )


def _create_slide_recovery_service(
    session: Session, settings: Settings
) -> SlideRecoveryWorkflowService:
    return SlideRecoveryWorkflowService(session, settings=settings)


def _set_slide_recovery_job_result(
    job: BackgroundWorkflowJob, result: SlideRecoveryWorkflowResult
) -> None:
    if not isinstance(result, SlideRecoveryWorkflowResult):
        raise TypeError("expected SlideRecoveryWorkflowResult")
    job.result = result
    job.workflow_run_id = result.workflow_run.id
    if result.awaiting_review:
        _set_job_status(job, BackgroundJobStatus.AWAITING_REVIEW)
    elif result.succeeded:
        _set_job_status(job, BackgroundJobStatus.COMPLETED)
    else:
        _set_job_status(job, BackgroundJobStatus.FAILED)
        job.error = "; ".join(result.errors) or "页面复活未完成"


def _create_visual_service(
    session: Session, settings: Settings, *, use_llm: bool
) -> VisualWorkflowService:
    llm = create_llm_provider(settings) if use_llm and settings.llm_configured else None
    return VisualWorkflowService(
        session,
        llm=llm,
        settings=settings,
        checkpointer_manager=get_workflow_checkpointer_manager(settings),
    )


def _set_job_status(job: BackgroundWorkflowJob, status: BackgroundJobStatus) -> None:
    job.status = status


def _set_planning_job_result(job: BackgroundWorkflowJob, result: PlanningWorkflowResult) -> None:
    if not isinstance(result, PlanningWorkflowResult):
        raise TypeError("expected PlanningWorkflowResult")
    job.result = result
    job.workflow_run_id = result.workflow_run.id
    if result.awaiting_review:
        _set_job_status(job, BackgroundJobStatus.AWAITING_REVIEW)
    elif result.succeeded:
        _set_job_status(job, BackgroundJobStatus.COMPLETED)
    else:
        _set_job_status(job, BackgroundJobStatus.FAILED)
        job.error = "; ".join(result.errors) or "规划工作流完成但存在错误"


def _set_visual_job_result(job: BackgroundWorkflowJob, result: VisualWorkflowResult) -> None:
    if not isinstance(result, VisualWorkflowResult):
        raise TypeError("expected VisualWorkflowResult")
    job.result = result
    job.workflow_run_id = result.workflow_run.id
    if result.awaiting_review:
        _set_job_status(job, BackgroundJobStatus.AWAITING_REVIEW)
    elif result.succeeded:
        _set_job_status(job, BackgroundJobStatus.COMPLETED)
    else:
        _set_job_status(job, BackgroundJobStatus.FAILED)
        job.error = "; ".join(result.errors) or "视觉编排未完成"


def _set_presentation_job_result(job: BackgroundWorkflowJob, result: WorkflowRunResult) -> None:
    job.result = result
    job.workflow_run_id = result.workflow_run.id
    if result.awaiting_review:
        _set_job_status(job, BackgroundJobStatus.AWAITING_REVIEW)
    elif result.succeeded:
        _set_job_status(job, BackgroundJobStatus.COMPLETED)
    else:
        _set_job_status(job, BackgroundJobStatus.FAILED)
        job.error = "; ".join(result.errors) or "工作流完成但存在错误"


def _run_presentation_job(
    job: BackgroundWorkflowJob,
    *,
    request: PresentationRequest,
    settings: Settings,
    export_kwargs: dict[str, Any],
) -> None:
    _set_job_status(job, BackgroundJobStatus.RUNNING)
    try:
        with get_session(scoped=False) as session:
            llm = create_llm_provider(settings)
            service = _create_presentation_service(session, llm, settings)
            try:
                workflow_run = service.prepare_run(job.project_id, request, **export_kwargs)
                job.workflow_run_id = workflow_run.id
                result = service.execute_prepared(workflow_run.id)
                _set_presentation_job_result(job, result)
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
        with get_session(scoped=False) as session:
            llm = create_llm_provider(settings)
            service = _create_presentation_service(session, llm, settings)
            try:
                result = service.continue_after_review(job.workflow_run_id)
                _set_presentation_job_result(job, result)
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
    # WF-002: refuse duplicate continue jobs for the same run while one is active.
    with _LOCK:
        for existing in _REGISTRY.values():
            if (
                existing.workflow_run_id == workflow_run_id
                and existing.status
                in {BackgroundJobStatus.PENDING, BackgroundJobStatus.RUNNING}
                and existing.kind == "presentation"
            ):
                raise WorkflowError(
                    f"工作流 {workflow_run_id} 已有后台 continue 在执行中，请勿重复提交"
                )
    manager = get_workflow_checkpointer_manager(resolved)
    if manager.is_run_busy(str(workflow_run_id)):
        raise WorkflowError(
            f"工作流 {workflow_run_id} 正在执行中，请等待完成后再继续"
        )
    job = BackgroundWorkflowJob(
        job_id=str(uuid4()),
        project_id=project_id,
        workflow_run_id=workflow_run_id,
        kind="presentation",
    )
    start_background_thread(
        job,
        lambda: _run_continue_job(job, settings=resolved),
    )
    return job


def _run_planning_job(
    job: BackgroundWorkflowJob,
    *,
    action: PlanningJobAction,
    settings: Settings,
    task_description: str | None = None,
    workflow_run_id: UUID | None = None,
    export_kwargs: dict[str, Any] | None = None,
) -> None:
    _set_job_status(job, BackgroundJobStatus.RUNNING)
    if workflow_run_id is not None:
        job.workflow_run_id = workflow_run_id
    try:
        with get_session(scoped=False) as session:
            service = _create_planning_service(session, settings)
            try:
                if action == PlanningJobAction.START:
                    if not task_description:
                        raise WorkflowError("任务描述不能为空")
                    result = service.run(job.project_id, task_description)
                    _set_planning_job_result(job, result)
                elif action == PlanningJobAction.CONTINUE_MISSION_CORRECTION:
                    if workflow_run_id is None:
                        raise WorkflowError("缺少 workflow_run_id")
                    result = service.continue_after_mission_correction(workflow_run_id)
                    _set_planning_job_result(job, result)
                elif action == PlanningJobAction.APPROVE_MISSION:
                    if workflow_run_id is None:
                        raise WorkflowError("缺少 workflow_run_id")
                    result = service.approve_mission_and_continue(workflow_run_id)
                    _set_planning_job_result(job, result)
                elif action == PlanningJobAction.CONTINUE_CLARIFICATION:
                    if workflow_run_id is None:
                        raise WorkflowError("缺少 workflow_run_id")
                    result = service.continue_after_clarification(workflow_run_id)
                    _set_planning_job_result(job, result)
                elif action == PlanningJobAction.START_PRESENTATION:
                    if workflow_run_id is None:
                        raise WorkflowError("缺少 workflow_run_id")
                    from archium.ui.planning_service import start_presentation_from_planning

                    presentation_result = start_presentation_from_planning(
                        session,
                        job.project_id,
                        workflow_run_id,
                        settings=settings,
                        **(export_kwargs or {}),
                    )
                    _set_presentation_job_result(job, presentation_result)
                    job.kind = "planning_presentation"
                else:
                    raise WorkflowError(f"Unknown planning action: {action}")
            finally:
                service.close()
    except WorkflowError as exc:
        job.error = str(exc)
        _set_job_status(job, BackgroundJobStatus.FAILED)
    except Exception as exc:
        job.error = str(exc)
        _set_job_status(job, BackgroundJobStatus.FAILED)


def submit_planning_job(
    project_id: UUID,
    action: PlanningJobAction,
    *,
    settings: Settings | None = None,
    task_description: str | None = None,
    workflow_run_id: UUID | None = None,
    **export_kwargs: Any,
) -> BackgroundWorkflowJob:
    """Run a planning workflow action in a background thread."""
    resolved = _resolve_settings(settings)
    job = BackgroundWorkflowJob(
        job_id=str(uuid4()),
        project_id=project_id,
        workflow_run_id=workflow_run_id,
        kind="planning",
        action=action.value,
    )
    start_background_thread(
        job,
        lambda: _run_planning_job(
            job,
            action=action,
            settings=resolved,
            task_description=task_description,
            workflow_run_id=workflow_run_id,
            export_kwargs=export_kwargs,
        ),
    )
    return job


def _run_visual_job(
    job: BackgroundWorkflowJob,
    *,
    action: VisualJobAction,
    settings: Settings,
    presentation_id: UUID,
    run_kwargs: dict[str, Any],
    workflow_run_id: UUID | None = None,
    allow_invalid_layout_export: bool = False,
) -> None:
    _set_job_status(job, BackgroundJobStatus.RUNNING)
    job.presentation_id = presentation_id
    if workflow_run_id is not None:
        job.workflow_run_id = workflow_run_id
    use_llm = bool(run_kwargs.get("use_llm", False))
    try:
        with get_session(scoped=False) as session:
            service = _create_visual_service(session, settings, use_llm=use_llm)
            try:
                if action == VisualJobAction.RUN:
                    result = service.run(job.project_id, presentation_id, **run_kwargs)
                    _set_visual_job_result(job, result)
                elif action == VisualJobAction.CONTINUE_LAYOUT_REVIEW:
                    if workflow_run_id is None:
                        raise WorkflowError("缺少 workflow_run_id")
                    result = service.continue_after_layout_review(
                        workflow_run_id,
                        allow_invalid_layout_export=allow_invalid_layout_export,
                    )
                    _set_visual_job_result(job, result)
                else:
                    raise WorkflowError(f"Unknown visual action: {action}")
            finally:
                service.close()
    except WorkflowError as exc:
        job.error = str(exc)
        _set_job_status(job, BackgroundJobStatus.FAILED)
    except Exception as exc:
        job.error = str(exc)
        _set_job_status(job, BackgroundJobStatus.FAILED)


def submit_visual_job(
    project_id: UUID,
    presentation_id: UUID,
    action: VisualJobAction,
    *,
    settings: Settings | None = None,
    workflow_run_id: UUID | None = None,
    allow_invalid_layout_export: bool = False,
    **run_kwargs: Any,
) -> BackgroundWorkflowJob:
    """Run a visual composition workflow action in a background thread."""
    resolved = _resolve_settings(settings)
    job = BackgroundWorkflowJob(
        job_id=str(uuid4()),
        project_id=project_id,
        presentation_id=presentation_id,
        workflow_run_id=workflow_run_id,
        kind="visual",
        action=action.value,
    )
    start_background_thread(
        job,
        lambda: _run_visual_job(
            job,
            action=action,
            settings=resolved,
            presentation_id=presentation_id,
            run_kwargs=run_kwargs,
            workflow_run_id=workflow_run_id,
            allow_invalid_layout_export=allow_invalid_layout_export,
        ),
    )
    return job


def _run_slide_recovery_job(
    job: BackgroundWorkflowJob,
    *,
    action: SlideRecoveryJobAction,
    settings: Settings,
    request: SlideRecoveryWorkflowRequest,
    workflow_run_id: UUID | None = None,
    review_accepted: bool = True,
    review_notes: str | None = None,
) -> None:
    _set_job_status(job, BackgroundJobStatus.RUNNING)
    if workflow_run_id is not None:
        job.workflow_run_id = workflow_run_id
    try:
        with get_session(scoped=False) as session:
            service = _create_slide_recovery_service(session, settings)
            if action == SlideRecoveryJobAction.RUN:
                result = service.run(job.project_id, request)
                _set_slide_recovery_job_result(job, result)
            elif action == SlideRecoveryJobAction.CONTINUE_REVIEW:
                if workflow_run_id is None:
                    raise WorkflowError("缺少 workflow_run_id")
                result = service.continue_after_review(
                    workflow_run_id,
                    accepted=review_accepted,
                    notes=review_notes,
                )
                _set_slide_recovery_job_result(job, result)
            else:
                raise WorkflowError(f"Unknown slide recovery action: {action}")
    except WorkflowError as exc:
        job.error = str(exc)
        _set_job_status(job, BackgroundJobStatus.FAILED)
    except Exception as exc:
        job.error = str(exc)
        _set_job_status(job, BackgroundJobStatus.FAILED)


def submit_slide_recovery_job(
    project_id: UUID,
    action: SlideRecoveryJobAction,
    *,
    request: SlideRecoveryWorkflowRequest,
    settings: Settings | None = None,
    workflow_run_id: UUID | None = None,
    review_accepted: bool = True,
    review_notes: str | None = None,
) -> BackgroundWorkflowJob:
    """Run slide recovery in a background thread."""
    resolved = _resolve_settings(settings)
    job = BackgroundWorkflowJob(
        job_id=str(uuid4()),
        project_id=project_id,
        workflow_run_id=workflow_run_id,
        kind="slide_recovery",
        action=action.value,
    )
    start_background_thread(
        job,
        lambda: _run_slide_recovery_job(
            job,
            action=action,
            settings=resolved,
            request=request,
            workflow_run_id=workflow_run_id,
            review_accepted=review_accepted,
            review_notes=review_notes,
        ),
    )
    return job


def find_running_workflow_run_id(
    project_id: UUID,
    *,
    workflow_kind: str | None = None,
    presentation_id: UUID | None = None,
) -> UUID | None:
    """Return the newest in-flight workflow run for a project (browser refresh recovery)."""
    with get_session(scoped=False) as session:
        runs = WorkflowRunRepository(session).list_by_project(project_id)
    for run in runs:
        if run.status != WorkflowStatus.RUNNING:
            continue
        kind = run.state.get("workflow_kind")
        if workflow_kind == "planning" and kind != "planning":
            continue
        if workflow_kind == "visual" and kind != "visual_composition":
            continue
        if workflow_kind == "slide_recovery" and kind != "slide_recovery":
            continue
        if workflow_kind == "presentation" and kind in {
            "planning",
            "visual_composition",
            "slide_recovery",
        }:
            continue
        if presentation_id is not None and run.presentation_id != presentation_id:
            continue
        return run.id
    return None


def load_workflow_result(
    workflow_run_id: UUID,
    *,
    settings: Settings | None = None,
) -> WorkflowRunResult:
    """Load a presentation WorkflowRunResult from persisted DB state."""
    resolved = _resolve_settings(settings)
    with get_session(scoped=False) as session:
        llm = create_llm_provider(resolved)
        service = _create_presentation_service(session, llm, resolved)
        try:
            return cast(WorkflowRunResult, service.result_from_run(workflow_run_id))
        finally:
            service.close()


def load_planning_result(
    workflow_run_id: UUID, *, settings: Settings | None = None
) -> PlanningWorkflowResult:
    """Load a planning workflow result from persisted DB state."""
    resolved = _resolve_settings(settings)
    with get_session(scoped=False) as session:
        service = _create_planning_service(session, resolved)
        try:
            return cast(PlanningWorkflowResult, service.result_from_run(workflow_run_id))
        finally:
            service.close()


def load_slide_recovery_result(
    workflow_run_id: UUID, *, settings: Settings | None = None
) -> SlideRecoveryWorkflowResult:
    """Load a slide recovery workflow result from persisted DB state."""
    resolved = _resolve_settings(settings)
    with get_session(scoped=False) as session:
        service = _create_slide_recovery_service(session, resolved)
        return service.result_from_run(workflow_run_id)


def load_visual_result(
    workflow_run_id: UUID, *, settings: Settings | None = None
) -> VisualWorkflowResult:
    """Load a visual workflow result from persisted DB state."""
    resolved = _resolve_settings(settings)
    with get_session(scoped=False) as session:
        service = _create_visual_service(session, resolved, use_llm=False)
        try:
            return cast(VisualWorkflowResult, service.result_from_run(workflow_run_id))
        finally:
            service.close()


def background_workflows_enabled(settings: Settings | None = None) -> bool:
    resolved = _resolve_settings(settings)
    return resolved.streamlit_background_workflows_enabled
