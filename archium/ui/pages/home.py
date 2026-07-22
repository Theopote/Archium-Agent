"""Archium home — project cockpit."""

from __future__ import annotations

import streamlit as st

from archium.ui.app_navigation import get_app_page
from archium.ui.product_flow import primary_stages, product_flow_chain, product_flow_home_steps
from archium.ui.project_progress_card import (
    ProjectProgressSnapshot,
    continue_work_page_key,
    greeting_for_now,
    list_recent_project_snapshots,
    load_cockpit_task_summary,
    _format_relative_time,
)


def _select_and_continue(snapshot: ProjectProgressSnapshot) -> None:
    st.session_state.selected_project_id = str(snapshot.project_id)
    if snapshot.presentation_id is not None:
        st.session_state.selected_presentation_id = str(snapshot.presentation_id)
    st.switch_page(get_app_page(continue_work_page_key(snapshot)))


def _render_greeting_and_create(*, has_projects: bool) -> None:
    left, right = st.columns([3.2, 1])
    with left:
        if has_projects:
            st.markdown(f"### {greeting_for_now()}，继续处理哪个项目？")
            st.caption("从最近项目接着做，或查看当前待办与快捷入口。")
        else:
            st.markdown(f"### {greeting_for_now()}，开始第一个项目")
            st.caption("创建项目后，按资料 → 大纲 → 生成 → 工作室 → 交付推进汇报。")
    with right:
        if st.button("新建项目", type="primary", use_container_width=True, key="home_new_project"):
            st.session_state.show_create_form = True
            st.switch_page(get_app_page("project-management"))


def _render_recent_projects(snapshots: list[ProjectProgressSnapshot]) -> None:
    st.markdown("#### 最近项目")
    if not snapshots:
        st.info("还没有项目。点击「新建项目」开始。")
        return

    for snapshot in snapshots:
        with st.container(border=True):
            title_col, action_col = st.columns([3.4, 1])
            with title_col:
                st.markdown(f"**{snapshot.project_name}**")
                st.caption(
                    f"{snapshot.presentation_type_label}"
                    f" · 当前阶段：{snapshot.current_stage_label}"
                    f" · {snapshot.completion_label}"
                    f" · 待处理 {snapshot.pending_count} 页"
                    f" · {_format_relative_time(snapshot.updated_at)}"
                )
                if snapshot.presentation_title:
                    st.caption(f"汇报：{snapshot.presentation_title}")
            with action_col:
                if st.button(
                    "继续工作",
                    key=f"home_continue_{snapshot.project_id}",
                    use_container_width=True,
                    type="primary",
                ):
                    _select_and_continue(snapshot)


def _render_current_tasks(snapshot: ProjectProgressSnapshot | None) -> None:
    st.markdown("#### 当前任务")
    if snapshot is None:
        st.caption("创建或选择项目后，这里会汇总待处理事项。")
        return

    try:
        tasks = load_cockpit_task_summary(snapshot)
    except Exception:
        st.caption("任务摘要暂不可用。可到工作室查看逐页状态。")
        return

    st.caption(f"聚焦：{snapshot.project_name}")
    if not tasks.has_tasks:
        if snapshot.ready_for_export:
            st.success("暂无阻塞项，可以前往交付导出。")
        else:
            st.info("暂无紧急任务。可继续生成或进入工作室微调。")
        return

    for line in tasks.lines:
        st.markdown(f"- {line}")


def _render_shortcuts(snapshot: ProjectProgressSnapshot | None) -> None:
    from archium.ui import icons

    st.markdown("#### 快捷入口")
    row1 = st.columns(2)
    with row1[0]:
        st.page_link(get_app_page("materials"), label="上传资料", icon=icons.UPLOAD)
    with row1[1]:
        st.page_link(get_app_page("edit"), label="继续编辑", icon=icons.STUDIO)
    row2 = st.columns(2)
    with row2[0]:
        st.page_link(get_app_page("edit"), label="待复核页面", icon=icons.CHECK)
    with row2[1]:
        st.page_link(get_app_page("deliver"), label="导出最新版本", icon=icons.EXPORT)

    if snapshot is not None:
        st.caption(
            f"当前项目「{snapshot.project_name}」建议下一步："
            f"{snapshot.current_stage_label}"
        )


def _render_first_run_guide(*, expanded: bool) -> None:
    with st.expander("五阶段说明（首次使用）", expanded=expanded):
        st.caption(f"推荐主流程：{product_flow_chain()}")
        for index, line in enumerate(product_flow_home_steps(), start=1):
            st.markdown(f"{index}. {line}")
        # Vertical / stacked links — readable on narrow windows (avoid 5-column squeeze).
        for stage in primary_stages():
            st.page_link(get_app_page(stage.page_key), label=f"{stage.title} — {stage.caption}", icon=stage.icon)


def render() -> None:
    try:
        snapshots = list_recent_project_snapshots(limit=6)
    except Exception:
        snapshots = []

    primary = snapshots[0] if snapshots else None
    # Prefer session-selected project when it appears in recent list.
    selected = st.session_state.get("selected_project_id")
    if selected and snapshots:
        for item in snapshots:
            if str(item.project_id) == str(selected):
                primary = item
                break

    _render_greeting_and_create(has_projects=bool(snapshots))
    st.divider()
    _render_recent_projects(snapshots)
    st.divider()
    _render_current_tasks(primary)
    st.divider()
    _render_shortcuts(primary)
    st.divider()
    _render_first_run_guide(expanded=not bool(snapshots))
