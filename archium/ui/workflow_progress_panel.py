"""Streamlit UI for polling and streaming workflow progress."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from uuid import UUID

import streamlit as st

from archium.application.workflow_progress import (
    STATUS_LABELS,
    format_step_log_entry,
    snapshot_from_run,
)
from archium.domain.enums import WorkflowStatus
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import WorkflowRunRepository
from archium.infrastructure.database.session import get_session
from archium.ui.background_workflow_runner import (
    BackgroundJobStatus,
    BackgroundWorkflowJob,
    find_running_workflow_run_id,
    get_job,
    load_planning_result,
    load_visual_result,
    load_workflow_result,
)
from archium.ui.error_handlers import format_user_error

WorkflowScope = str  # "presentation" | "planning" | "visual"


def _session_job_key(
    project_id: UUID,
    scope: WorkflowScope = "presentation",
    *,
    presentation_id: UUID | None = None,
) -> str:
    if scope == "planning":
        return f"active_planning_wf_job_{project_id}"
    if scope == "visual" and presentation_id is not None:
        return f"active_visual_wf_job_{project_id}_{presentation_id}"
    return f"active_wf_job_{project_id}"


def get_active_job_id(
    project_id: UUID,
    scope: WorkflowScope = "presentation",
    *,
    presentation_id: UUID | None = None,
) -> str | None:
    return st.session_state.get(
        _session_job_key(project_id, scope, presentation_id=presentation_id)
    )


def set_active_job_id(
    project_id: UUID,
    job_id: str | None,
    scope: WorkflowScope = "presentation",
    *,
    presentation_id: UUID | None = None,
) -> None:
    st.session_state[_session_job_key(project_id, scope, presentation_id=presentation_id)] = job_id


def recover_active_workflow_run(
    project_id: UUID,
    scope: WorkflowScope = "presentation",
    *,
    presentation_id: UUID | None = None,
) -> UUID | None:
    """Reattach to a RUNNING workflow after browser refresh."""
    job_id = get_active_job_id(project_id, scope, presentation_id=presentation_id)
    if job_id:
        job = get_job(job_id)
        if job and job.workflow_run_id:
            return job.workflow_run_id
    workflow_kind = None
    if scope == "planning":
        workflow_kind = "planning"
    elif scope == "visual":
        workflow_kind = "visual"
    elif scope == "presentation":
        workflow_kind = "presentation"
    return find_running_workflow_run_id(
        project_id,
        workflow_kind=workflow_kind,
        presentation_id=presentation_id if scope == "visual" else None,
    )


def _terminal_statuses() -> set[BackgroundJobStatus]:
    return {
        BackgroundJobStatus.COMPLETED,
        BackgroundJobStatus.FAILED,
        BackgroundJobStatus.AWAITING_REVIEW,
    }


def _load_result_for_scope(
    scope: WorkflowScope,
    workflow_run_id: UUID,
    *,
    settings: Any = None,
) -> Any:
    if scope == "planning":
        return load_planning_result(workflow_run_id, settings=settings)
    if scope == "visual":
        return load_visual_result(workflow_run_id, settings=settings)
    return load_workflow_result(workflow_run_id, settings=settings)


def _default_success_message(scope: WorkflowScope, result: Any) -> str | None:
    if scope == "planning":
        return "规划工作流步骤已完成。"
    if scope == "visual":
        return "视觉编排完成。"
    slides = getattr(result, "slides", None) or []
    return f"汇报已生成，共 {len(slides)} 页。"


def _default_awaiting_message(scope: WorkflowScope) -> str:
    if scope == "planning":
        return "规划工作流已暂停，请按当前步骤继续审核或编辑。"
    if scope == "visual":
        return "视觉编排已暂停，请审核视觉方向或版式后继续。"
    return "工作流已暂停，请切换到「审核」标签页继续处理 Brief / Storyline。"


def _apply_job_completion(
    project_id: UUID,
    job: BackgroundWorkflowJob,
    *,
    scope: WorkflowScope,
    presentation_id: UUID | None,
    on_complete: Callable[[Any], None] | None,
    result_session_key: str | None,
    awaiting_review_message: str | None,
    success_message: str | Callable[[Any], str] | None,
    rerun_on_complete: bool,
) -> None:
    if job.status == BackgroundJobStatus.FAILED:
        st.error(job.error or "工作流执行失败")
        set_active_job_id(project_id, None, scope, presentation_id=presentation_id)
        return

    result = job.result
    if result is None and job.workflow_run_id is not None:
        try:
            result = _load_result_for_scope(scope, job.workflow_run_id)
        except WorkflowError as exc:
            st.error(format_user_error(exc))
            set_active_job_id(project_id, None, scope, presentation_id=presentation_id)
            return

    if result is not None:
        if result_session_key:
            st.session_state[result_session_key] = result
        if on_complete is not None:
            on_complete(result)

    if job.status == BackgroundJobStatus.AWAITING_REVIEW:
        st.warning(awaiting_review_message or _default_awaiting_message(scope))
    elif job.status == BackgroundJobStatus.COMPLETED:
        if callable(success_message):
            message = success_message(result)
        elif success_message:
            message = success_message
        else:
            message = _default_success_message(scope, result)
        if message:
            st.success(message)

    set_active_job_id(project_id, None, scope, presentation_id=presentation_id)
    if rerun_on_complete:
        st.rerun()


def _render_progress_body(workflow_run_id: UUID) -> None:
    with get_session() as session:
        run = WorkflowRunRepository(session).get_by_id(workflow_run_id)
    if run is None:
        st.info("正在启动工作流…")
        return

    snapshot = snapshot_from_run(run)
    status_label = STATUS_LABELS.get(snapshot.status, snapshot.status.value)

    col_status, col_step = st.columns([1, 3])
    with col_status:
        st.metric("状态", status_label)
    with col_step:
        st.markdown(f"**当前步骤：** {snapshot.current_step_label}")

    if snapshot.errors:
        for error in snapshot.errors[-3:]:
            st.caption(f"⚠ {error}")

    log_entries = snapshot.step_log[-12:]
    if log_entries:
        st.markdown("**执行日志**")
        log_box = st.container(border=True)
        with log_box:
            for entry in log_entries:
                st.caption(format_step_log_entry(entry))
    elif snapshot.current_step_label:
        st.caption(snapshot.current_step_label)


def _poll_once(
    project_id: UUID,
    *,
    scope: WorkflowScope,
    presentation_id: UUID | None,
    job_id: str | None,
    workflow_run_id: UUID | None,
    on_complete: Callable[[Any], None] | None,
    result_session_key: str | None,
    awaiting_review_message: str | None,
    success_message: str | Callable[[Any], str] | None,
    rerun_on_complete: bool,
) -> bool:
    """Return True when polling should stop."""
    job = get_job(job_id) if job_id else None
    run_id = workflow_run_id
    if job is not None and job.workflow_run_id is not None:
        run_id = job.workflow_run_id
    elif job is not None and job.status == BackgroundJobStatus.RUNNING and run_id is None:
        kind = None
        if scope == "planning":
            kind = "planning"
        elif scope == "visual":
            kind = "visual"
        elif scope == "presentation":
            kind = "presentation"
        recovered = find_running_workflow_run_id(
            project_id,
            workflow_kind=kind,
            presentation_id=presentation_id if scope == "visual" else None,
        )
        if recovered is not None:
            job.workflow_run_id = recovered
            run_id = recovered

    if run_id is not None:
        _render_progress_body(run_id)

    if job is not None and job.status in _terminal_statuses():
        _apply_job_completion(
            project_id,
            job,
            scope=scope,
            presentation_id=presentation_id,
            on_complete=on_complete,
            result_session_key=result_session_key,
            awaiting_review_message=awaiting_review_message,
            success_message=success_message,
            rerun_on_complete=rerun_on_complete,
        )
        return True

    if job is None and run_id is not None:
        with get_session() as session:
            run = WorkflowRunRepository(session).get_by_id(run_id)
        if run is not None and run.status in {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.AWAITING_REVIEW,
        }:
            try:
                result = _load_result_for_scope(scope, run_id)
                if result_session_key:
                    st.session_state[result_session_key] = result
                if on_complete is not None:
                    on_complete(result)
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            if run.status == WorkflowStatus.AWAITING_REVIEW:
                st.warning(awaiting_review_message or _default_awaiting_message(scope))
            elif run.status == WorkflowStatus.COMPLETED:
                message = (
                    success_message(result)
                    if callable(success_message)
                    else success_message or _default_success_message(scope, result)
                )
                if message:
                    st.success(message)
            elif run.status == WorkflowStatus.FAILED:
                st.error("工作流执行失败。")
            set_active_job_id(project_id, None, scope, presentation_id=presentation_id)
            if rerun_on_complete:
                st.rerun()
            return True

    return False


def render_workflow_progress_panel(
    project_id: UUID,
    *,
    scope: WorkflowScope = "presentation",
    presentation_id: UUID | None = None,
    job_id: str | None = None,
    workflow_run_id: UUID | None = None,
    result_session_key: str | None = "last_workflow_result",
    on_complete: Callable[[Any], None] | None = None,
    awaiting_review_message: str | None = None,
    success_message: str | Callable[[Any], str] | None = None,
    poll_interval_seconds: float = 2.0,
    rerun_on_complete: bool = True,
) -> bool:
    """Poll workflow progress until terminal. Returns True when a job is active."""
    resolved_job_id = job_id or get_active_job_id(
        project_id, scope, presentation_id=presentation_id
    )
    resolved_run_id = workflow_run_id or recover_active_workflow_run(
        project_id, scope, presentation_id=presentation_id
    )

    if resolved_job_id is None and resolved_run_id is None:
        return False

    st.markdown("#### 工作流进度")
    placeholder = st.empty()

    def _draw() -> bool:
        with placeholder.container():
            return _poll_once(
                project_id,
                scope=scope,
                presentation_id=presentation_id,
                job_id=resolved_job_id,
                workflow_run_id=resolved_run_id,
                on_complete=on_complete,
                result_session_key=result_session_key,
                awaiting_review_message=awaiting_review_message,
                success_message=success_message,
                rerun_on_complete=rerun_on_complete,
            )

    def _still_active() -> bool:
        job = get_job(resolved_job_id) if resolved_job_id else None
        if job is not None:
            return job.status not in _terminal_statuses()
        if resolved_run_id is not None:
            with get_session() as session:
                run = WorkflowRunRepository(session).get_by_id(resolved_run_id)
            return run is not None and run.status == WorkflowStatus.RUNNING
        return False

    if hasattr(st, "fragment"):
        run_every = timedelta(seconds=poll_interval_seconds)

        @st.fragment(run_every=run_every)
        def _fragment_poll() -> None:
            finished = _draw()
            if finished and rerun_on_complete:
                st.rerun(scope="app")

        _fragment_poll()
        return _still_active()

    finished = _draw()
    if not finished:
        refresh_key = f"wf_poll_refresh_{scope}_{project_id}"
        if presentation_id is not None:
            refresh_key = f"{refresh_key}_{presentation_id}"
        if st.button("刷新进度", key=refresh_key):
            st.rerun()
        st.caption("后台任务运行中；可点击刷新或等待自动片段轮询（Streamlit ≥1.33）。")
    return _still_active()
