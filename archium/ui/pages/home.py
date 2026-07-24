"""Archium home — focused project cockpit."""

from __future__ import annotations

import logging

import streamlit as st

from archium.domain.delivery_record import DeliveryRecord
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.product_flow import primary_stages, product_flow_chain, product_flow_home_steps
from archium.ui.project_progress_card import (
    ProjectProgressSnapshot,
    _format_relative_time,
    continue_work_page_key,
    greeting_for_now,
    list_recent_project_snapshots,
    load_cockpit_task_summary,
)
from archium.ui.workspace_service import list_project_presentations

logger = logging.getLogger(__name__)


def _select_and_continue(snapshot: ProjectProgressSnapshot) -> None:
    st.session_state.selected_project_id = str(snapshot.project_id)
    if snapshot.presentation_id is not None:
        st.session_state.selected_presentation_id = str(snapshot.presentation_id)
    st.switch_page(get_app_page(continue_work_page_key(snapshot)))


def _resolve_primary(snapshots: list[ProjectProgressSnapshot]) -> ProjectProgressSnapshot | None:
    if not snapshots:
        return None
    selected = st.session_state.get("selected_project_id")
    if selected:
        for item in snapshots:
            if str(item.project_id) == str(selected):
                return item
    return snapshots[0]


def _render_empty_state() -> None:
    from archium.ui.components.chrome import render_empty_state

    def _go_create() -> None:
        st.session_state.show_create_form = True
        st.switch_page(get_app_page("project-genesis"))

    render_empty_state(
        f"{greeting_for_now()}，开始第一个项目",
        "从一句话想法探索设计使命，或从已有资料整理汇报。",
        primary_label="开始项目",
        primary_key="home_new_project_empty",
        on_primary=_go_create,
    )
    with st.expander("五阶段说明（首次使用）", expanded=True):
        st.caption(f"推荐主流程：{product_flow_chain()}")
        for index, line in enumerate(product_flow_home_steps(), start=1):
            st.markdown(f"{index}. {line}")
        for stage in primary_stages():
            st.page_link(
                get_app_page(stage.page_key),
                label=f"{stage.title} — {stage.caption}",
                icon=stage.icon,
            )


def _render_load_failed(exc: Exception) -> None:
    from archium.ui import icons
    from archium.ui.components.chrome import (
        render_empty_state,
        render_error_callout,
        render_primary_action,
    )

    logger.exception("Failed to load home project snapshots: %s", exc)
    render_error_callout("项目列表暂时无法加载，请重试。")
    render_empty_state(
        "无法加载项目",
        "这通常是数据或连接问题，并不表示你没有项目。",
    )
    if render_primary_action("重试", key="home_retry_load", use_container_width=False):
        st.rerun()
    st.page_link(
        get_app_page("project-management"),
        label="前往项目管理",
        icon=icons.PROJECT,
    )


def _render_progress_bar(snapshot: ProjectProgressSnapshot) -> None:
    if snapshot.slide_count <= 0:
        st.progress(0.0, text=snapshot.completion_label)
        return
    ratio = min(1.0, snapshot.layout_ready_count / max(1, snapshot.slide_count))
    st.progress(ratio, text=snapshot.completion_label)


def _render_pending_issues(snapshot: ProjectProgressSnapshot) -> None:
    st.markdown("**待处理问题**")
    try:
        tasks = load_cockpit_task_summary(snapshot)
    except Exception:
        logger.exception("Failed to load cockpit task summary")
        st.caption("任务摘要暂不可用。")
        return
    if not tasks.has_tasks:
        if snapshot.ready_for_export:
            st.success("暂无阻塞项，可以前往交付导出。")
        else:
            st.info("暂无紧急问题。")
        return
    for line in tasks.lines:
        st.markdown(f"- {line}")


def _render_recent_versions(snapshot: ProjectProgressSnapshot) -> None:
    st.markdown("**最近版本**")
    try:
        with get_session() as session:
            presentations = list_project_presentations(session, snapshot.project_id)
    except Exception:
        logger.exception("Failed to list presentations for home")
        presentations = []

    export_records: list[DeliveryRecord | dict[str, object]] = []
    try:
        from archium.application.delivery_record_service import DeliveryRecordService

        with get_session() as session:
            export_records = [
                record
                for record in DeliveryRecordService(session).list_for_project(
                    snapshot.project_id, limit=4
                )
            ]
    except Exception:
        export_records = [
            record
            for record in (st.session_state.get("delivery_export_records") or [])
            if str(record.get("project_id") or "") in {"", str(snapshot.project_id)}
        ]

    if presentations:
        for presentation in presentations[:4]:
            st.caption(
                f"{presentation.title} · {presentation.status.value} · "
                f"{presentation.updated_at.strftime('%Y-%m-%d %H:%M')}"
            )
    if export_records:
        st.caption("最近导出")
        for record in export_records[:4]:
            if isinstance(record, DeliveryRecord):
                when = record.exported_at.astimezone().strftime("%Y-%m-%d %H:%M")
                st.caption(f"{record.format} · {when} · `{record.file_uri}`")
            else:
                st.caption(
                    f"{record.get('format', '导出')} · {record.get('when', '')} · "
                    f"`{record.get('path', '')}`"
                )
    if not presentations and not export_records:
        st.caption("尚无汇报版本。完成生成或导出后会显示在此。")


def _task_statement_for(snapshot: ProjectProgressSnapshot) -> str:
    """Prefer mission/brief task text; fall back to presentation title/type."""
    try:
        from archium.ui.pages import project_mission

        planning = project_mission.load_planning_snapshot(snapshot.project_id)
        if planning.mission is not None and planning.mission.task_statement.strip():
            return planning.mission.task_statement.strip()
        if planning.presentation_request is not None:
            request = planning.presentation_request
            bits = [request.title, request.purpose or request.core_message]
            text = " — ".join(part for part in bits if part)
            if text:
                return text
    except Exception:
        logger.exception("Failed to load planning snapshot for home task statement")
    if snapshot.presentation_title:
        return snapshot.presentation_title
    return snapshot.presentation_type_label


def _render_project_cockpit(snapshot: ProjectProgressSnapshot) -> None:
    header_l, header_r = st.columns([3.2, 1])
    with header_l:
        st.markdown(f"### {snapshot.project_name}")
        st.caption(f"{greeting_for_now()} · 当前项目工作台")
    with header_r:
        if st.button("切换项目", use_container_width=True, key="home_switch_project"):
            st.switch_page(get_app_page("project-management"))

    st.markdown(f"**汇报任务**  \n{_task_statement_for(snapshot)}")

    if snapshot.outline_changes_pending:
        st.warning("大纲已编辑 · 待重新确认后再进入生成。")

    meta = st.columns(3)
    with meta[0]:
        st.markdown(f"**当前阶段**  \n{snapshot.current_stage_label}")
    with meta[1]:
        st.markdown(f"**大纲**  \n{snapshot.outline_label}")
    with meta[2]:
        st.markdown("**总体进度**")
        _render_progress_bar(snapshot)

    st.divider()
    left, right = st.columns(2)
    with left:
        _render_pending_issues(snapshot)
    with right:
        _render_recent_versions(snapshot)

    st.divider()
    cta_l, cta_r = st.columns([2, 1])
    with cta_l:
        if st.button(
            "继续工作",
            type="primary",
            use_container_width=True,
            key="home_continue_primary",
        ):
            _select_and_continue(snapshot)
    with cta_r:
        st.caption(f"建议进入：{snapshot.current_stage_label}")


def _render_other_projects(
    snapshots: list[ProjectProgressSnapshot],
    *,
    primary: ProjectProgressSnapshot,
) -> None:
    others = [item for item in snapshots if item.project_id != primary.project_id]
    if not others:
        return
    with st.expander("其他最近项目", expanded=False):
        for snapshot in others:
            cols = st.columns([3.4, 1])
            with cols[0]:
                st.markdown(f"**{snapshot.project_name}**")
                st.caption(
                    f"{snapshot.current_stage_label} · {snapshot.completion_label} · "
                    f"{_format_relative_time(snapshot.updated_at)}"
                )
            with cols[1]:
                if st.button(
                    "继续工作",
                    key=f"home_open_{snapshot.project_id}",
                    use_container_width=True,
                    help="设为当前项目并进入建议阶段",
                ):
                    _select_and_continue(snapshot)


def render() -> None:
    try:
        snapshots = list_recent_project_snapshots(limit=6)
    except Exception as exc:
        _render_load_failed(exc)
        return

    primary = _resolve_primary(snapshots)
    if primary is None:
        _render_empty_state()
        return

    _render_project_cockpit(primary)
    _render_other_projects(snapshots, primary=primary)
    with st.expander("五阶段说明（首次使用）", expanded=False):
        st.caption(f"推荐主流程：{product_flow_chain()}")
        for index, line in enumerate(product_flow_home_steps(), start=1):
            st.markdown(f"{index}. {line}")
