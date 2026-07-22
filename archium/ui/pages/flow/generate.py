"""Product-flow stage: 生成 — page queue + recovery CTAs."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.generate_queue import GenerateQueueMetrics, metrics_from_board, queue_row_status
from archium.ui.page_status_board_panel import (
    load_page_status_board,
    render_compact_page_actions,
)
from archium.ui.pages.flow import (
    render_flow_project_context,
    render_stage_header,
    render_stage_nav,
)
from archium.ui.pages.workspace import render_generate_stage
from archium.ui.product_flow import product_studio_page_key
from archium.ui.project_progress_card import load_project_progress_snapshot
from archium.ui.workspace_service import list_project_presentations


def _selected_presentation_id(project_id: UUID) -> UUID | None:
    selected = st.session_state.get("selected_presentation_id")
    with get_session() as session:
        presentations = list_project_presentations(session, project_id)
    if not presentations:
        return None
    ids = [str(item.id) for item in presentations]
    if selected in ids:
        return UUID(str(selected))
    st.session_state.selected_presentation_id = ids[0]
    return presentations[0].id


def _resolve_flow_project_id() -> UUID | None:
    raw = render_flow_project_context(allow_create=False, key_prefix="generate")
    if raw is None:
        return None
    if isinstance(raw, UUID):
        return raw
    return UUID(str(raw))


def _render_queue_summary(metrics: GenerateQueueMetrics) -> None:
    st.markdown(
        f"**总体 {metrics.complete}/{metrics.total}**　"
        f"完成 {metrics.complete}　"
        f"待处理 {metrics.pending}　"
        f"失败 {metrics.failed}"
    )


def _render_page_queue(project_id: UUID, presentation_id: UUID) -> bool:
    """Return True when any attention rows exist."""
    board = load_page_status_board(presentation_id)
    metrics = metrics_from_board(board)
    _render_queue_summary(metrics)

    if not board.rows:
        st.info("尚未生成页面。展开下方「运行汇报管线」开始生成。")
        return False

    st.markdown("#### 逐页队列")
    has_attention = False
    for row in board.rows:
        attention = row.severity in {"warn", "error"}
        if attention:
            has_attention = True
        status = queue_row_status(row)
        title = (row.title or f"第 {row.order + 1} 页").strip()
        # Spec shape: 01 封面              完成
        line = f"`{row.order + 1:02d}`  **{title}**"
        cols = st.columns([4.2, 1.4])
        with cols[0]:
            st.markdown(line)
            if attention and row.detail:
                st.caption(row.detail)
        with cols[1]:
            st.markdown(status)
        if attention:
            render_compact_page_actions(
                presentation_id=presentation_id,
                project_id=project_id,
                row=row,
                key_prefix="generate_queue",
            )
    return has_attention


def _render_bottom_actions(*, has_attention: bool, ready_for_export: bool) -> None:
    st.divider()
    cols = st.columns(2)
    with cols[0]:
        if st.button(
            "处理问题页",
            type="primary" if has_attention else "secondary",
            use_container_width=True,
            disabled=not has_attention,
            help=None if has_attention else "当前没有需要处理的问题页",
        ):
            st.session_state["studio_focus_attention"] = True
            st.switch_page(get_app_page(product_studio_page_key()))
    with cols[1]:
        if st.button("进入工作室", type="primary", use_container_width=True):
            st.switch_page(get_app_page(product_studio_page_key()))
    if ready_for_export:
        from archium.ui import icons

        st.page_link(get_app_page("deliver"), label="版式已齐，前往交付", icon=icons.DELIVER)


def render() -> None:
    render_stage_header("generate")
    st.caption("主体是逐页队列。版式微调请到「工作室」；导出在「交付」。")
    project_id = _resolve_flow_project_id()
    if project_id is None:
        st.info("请先在「资料」阶段创建或选择项目。")
        render_stage_nav("generate")
        return

    presentation_id = _selected_presentation_id(project_id)
    has_attention = False
    if presentation_id is not None:
        try:
            has_attention = _render_page_queue(project_id, presentation_id)
        except Exception:
            st.warning("逐页状态暂不可用。可先运行汇报管线。")
    else:
        st.info("当前项目尚无汇报。展开下方「运行汇报管线」创建并生成。")

    with st.expander("运行汇报管线", expanded=presentation_id is None):
        render_generate_stage(project_id, include_export=False)

    snapshot = None
    try:
        snapshot = load_project_progress_snapshot()
    except Exception:
        snapshot = None
    ready = bool(snapshot and snapshot.ready_for_export)
    _render_bottom_actions(has_attention=has_attention, ready_for_export=ready)
    render_stage_nav("generate")
