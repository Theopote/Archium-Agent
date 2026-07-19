"""Streamlit UI for polling and streaming workflow progress."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
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
    load_workflow_result,
)
from archium.ui.error_handlers import format_user_error


def _session_job_key(project_id: UUID) -> str:
    return f"active_wf_job_{project_id}"


def get_active_job_id(project_id: UUID) -> str | None:
    return st.session_state.get(_session_job_key(project_id))


def set_active_job_id(project_id: UUID, job_id: str | None) -> None:
    st.session_state[_session_job_key(project_id)] = job_id


def recover_active_workflow_run(project_id: UUID) -> UUID | None:
    """Reattach to a RUNNING workflow after browser refresh."""
    if get_active_job_id(project_id):
        job = get_job(get_active_job_id(project_id) or "")
        if job and job.workflow_run_id:
            return job.workflow_run_id
    return find_running_workflow_run_id(project_id)


def _terminal_statuses() -> set[BackgroundJobStatus]:
    return {
        BackgroundJobStatus.COMPLETED,
        BackgroundJobStatus.FAILED,
        BackgroundJobStatus.AWAITING_REVIEW,
    }


def _apply_job_completion(
    project_id: UUID,
    job: BackgroundWorkflowJob,
    *,
    on_complete: Callable[[object], None] | None,
    result_session_key: str,
) -> None:
    if job.status == BackgroundJobStatus.FAILED:
        st.error(job.error or "工作流执行失败")
        set_active_job_id(project_id, None)
        return
    if job.result is not None:
        st.session_state[result_session_key] = job.result
        if on_complete is not None:
            on_complete(job.result)
    elif job.workflow_run_id is not None:
        try:
            result = load_workflow_result(job.workflow_run_id)
            st.session_state[result_session_key] = result
            if on_complete is not None:
                on_complete(result)
        except WorkflowError as exc:
            st.error(format_user_error(exc))
            set_active_job_id(project_id, None)
            return

    if job.status == BackgroundJobStatus.AWAITING_REVIEW:
        st.warning("工作流已暂停，请切换到「审核」标签页继续处理 Brief / Storyline。")
    elif job.status == BackgroundJobStatus.COMPLETED:
        result = st.session_state.get(result_session_key)
        slide_count = len(getattr(result, "slides", []) or [])
        st.success(f"汇报已生成，共 {slide_count} 页。")
    set_active_job_id(project_id, None)


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
    job_id: str | None,
    workflow_run_id: UUID | None,
    on_complete: Callable[[object], None] | None,
    result_session_key: str,
) -> bool:
    """Return True when polling should stop."""
    job = get_job(job_id) if job_id else None
    run_id = workflow_run_id
    if job is not None and job.workflow_run_id is not None:
        run_id = job.workflow_run_id

    if run_id is not None:
        _render_progress_body(run_id)

    if job is not None and job.status in _terminal_statuses():
        _apply_job_completion(
            project_id,
            job,
            on_complete=on_complete,
            result_session_key=result_session_key,
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
                result = load_workflow_result(run_id)
                st.session_state[result_session_key] = result
                if on_complete is not None:
                    on_complete(result)
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            if run.status == WorkflowStatus.AWAITING_REVIEW:
                st.warning("工作流已暂停，请切换到「审核」标签页继续。")
            elif run.status == WorkflowStatus.COMPLETED:
                st.success("工作流已完成。")
            elif run.status == WorkflowStatus.FAILED:
                st.error("工作流执行失败。")
            set_active_job_id(project_id, None)
            return True

    return False


def render_workflow_progress_panel(
    project_id: UUID,
    *,
    job_id: str | None = None,
    workflow_run_id: UUID | None = None,
    result_session_key: str = "last_workflow_result",
    on_complete: Callable[[object], None] | None = None,
    poll_interval_seconds: float = 2.0,
) -> bool:
    """Poll workflow progress until terminal. Returns True when finished."""
    resolved_job_id = job_id or get_active_job_id(project_id)
    resolved_run_id = workflow_run_id or recover_active_workflow_run(project_id)

    if resolved_job_id is None and resolved_run_id is None:
        return False

    st.markdown("#### 工作流进度")
    placeholder = st.empty()

    def _draw() -> bool:
        with placeholder.container():
            return _poll_once(
                project_id,
                job_id=resolved_job_id,
                workflow_run_id=resolved_run_id,
                on_complete=on_complete,
                result_session_key=result_session_key,
            )

    if hasattr(st, "fragment"):
        run_every = timedelta(seconds=poll_interval_seconds)

        @st.fragment(run_every=run_every)
        def _fragment_poll() -> None:
            if _draw():
                st.rerun(scope="app")

        _fragment_poll()
        job = get_job(resolved_job_id) if resolved_job_id else None
        return job is not None and job.status in _terminal_statuses()

    finished = _draw()
    if not finished:
        if st.button("刷新进度", key=f"wf_poll_refresh_{project_id}"):
            st.rerun()
        st.caption("后台任务运行中；可点击刷新或等待自动片段轮询（Streamlit ≥1.33）。")
    return finished
