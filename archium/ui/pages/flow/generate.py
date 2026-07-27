"""Product-flow stage: 生成 — page queue + recovery CTAs."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.generate_queue import GenerateQueueMetrics, metrics_from_board, queue_row_status
from archium.ui.label_map import CONTENT_PIPELINE_ACTION
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
        from archium.application.presentation_selection import select_presentation

        presentations = list_project_presentations(session, project_id)
        picked = select_presentation(
            session,
            presentations,
            preferred_id=selected,
            # Auto-default: skip empty shells when another deck has pages.
            keep_empty_preferred=False,
        )
    if picked is None:
        return None
    st.session_state.selected_presentation_id = str(picked.id)
    return picked.id


def _resolve_flow_project_id() -> UUID | None:
    raw = render_flow_project_context(allow_create=False, key_prefix="generate")
    if raw is None:
        return None
    if isinstance(raw, UUID):
        return raw
    return UUID(str(raw))


def _render_project_context_readiness(project_id: UUID) -> None:
    """Surface project knowledge posture before the presentation pipeline."""
    from archium.application.context import (
        PresentationGateVerdict,
        build_project_context,
        presentation_readiness_from_context,
    )
    from archium.application.context.workflow_navigation import as_session_state
    from archium.application.project_knowledge_display import _partner_gap_text
    from archium.config.settings import get_settings
    from archium.ui.context_navigation import dispatch_next_best_action

    try:
        with get_session() as session:
            context = build_project_context(session, project_id)
        readiness = presentation_readiness_from_context(context)
    except Exception:
        st.caption("项目理解状态暂不可用")
        return

    if readiness.has_context and readiness.completeness_pct > 0:
        if readiness.completeness_pct < 45:
            st.caption(
                f"资料掌握约 {readiness.completeness_pct}%，可先出草稿；"
                "正式交付前建议继续补资料。"
            )
        else:
            st.caption(f"资料掌握约 {readiness.completeness_pct}%，可开始生成。")

    if readiness.verdict == PresentationGateVerdict.BLOCK:
        st.error("当前资料较少，正式汇报前建议先补充研究或澄清关键问题。")
    partner_warnings = [
        _partner_gap_text(line)
        for line in readiness.warnings
        if str(line).strip() and not str(line).strip().startswith("知识完整度约")
    ]
    if partner_warnings:
        st.warning("\n\n".join(partner_warnings))
    if readiness.suggested_action is not None:
        label = {
            "research": "补充研究",
            "explore_directions": "推演概念方向",
            "upload_materials": "整理资料",
            "ask": "澄清未知项",
            "open_mission": "打开任务",
            "generate_mission": "生成任务",
        }.get(readiness.suggested_action.value, readiness.suggested_action.value)
        if st.button(f"建议：{label}", key=f"generate_gate_{readiness.suggested_action.value}"):
            settings = get_settings()
            with get_session() as session:
                dispatch_next_best_action(
                    session,
                    as_session_state(st.session_state),
                    readiness.suggested_action,
                    project_id=project_id,
                    settings=settings,
                )


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
        st.info(f"尚未生成页面。展开下方「{CONTENT_PIPELINE_ACTION}」开始生成。")
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
            width="stretch",
            disabled=not has_attention,
            help=None if has_attention else "当前没有需要处理的问题页",
        ):
            st.session_state["studio_focus_attention"] = True
            st.switch_page(get_app_page(product_studio_page_key()))
    with cols[1]:
        if st.button("进入工作室", type="primary", width="stretch"):
            st.switch_page(get_app_page(product_studio_page_key()))
    if ready_for_export:
        from archium.ui import icons

        st.page_link(get_app_page("deliver"), label="版式已齐，前往交付", icon=icons.DELIVER)


def _render_starter_content_banner(project_id: UUID) -> None:
    from archium.application.genesis_starter_service import get_genesis_starter_state

    with get_session() as session:
        starter = get_genesis_starter_state(session, project_id)
    if starter is None:
        return
    if starter.slides_ready_count < starter.page_count:
        return
    snapshot = load_project_progress_snapshot()
    if snapshot is None:
        return

    if starter.layout_ready_count >= starter.page_count:
        st.success(
            f"Genesis 已为全稿生成 {starter.layout_ready_count} 页版式线框。"
            "可在工作室「全稿鸟瞰」浏览；运行下方管线可升级为正式版式与截图。"
        )
    elif snapshot.layout_ready_count >= snapshot.slide_count:
        return
    else:
        st.info(
            f"Genesis 已生成 {starter.slides_ready_count} 页内容占位"
            f"（{starter.layout_ready_count}/{starter.page_count} 页线框）。"
            "运行下方「内容生成管线」补齐正式版式，或到工作室浏览故事结构。"
        )

    cols = st.columns(2)
    with cols[0]:
        if st.button(
            "全稿鸟瞰",
            key=f"generate_deck_overview_{project_id}",
            width="stretch",
        ):
            st.session_state.studio_center_mode = "overview"
            st.switch_page(get_app_page(product_studio_page_key()))
    with cols[1]:
        if st.button(
            "进入工作室",
            key=f"generate_open_studio_{project_id}",
            width="stretch",
        ):
            st.switch_page(get_app_page(product_studio_page_key()))


def render() -> None:
    render_stage_header("generate")
    st.caption("主体是逐页队列。版式微调请到「工作室」；导出在「交付」。")
    project_id = _resolve_flow_project_id()
    if project_id is None:
        st.info("请先在「资料」阶段创建或选择项目。")
        render_stage_nav("generate")
        return

    _render_project_context_readiness(project_id)
    _render_starter_content_banner(project_id)

    presentation_id = _selected_presentation_id(project_id)
    has_attention = False
    if presentation_id is not None:
        try:
            has_attention = _render_page_queue(project_id, presentation_id)
        except Exception:
            st.warning(f"逐页状态暂不可用。可先{CONTENT_PIPELINE_ACTION}。")
    else:
        st.info(f"当前项目尚无汇报。展开下方「{CONTENT_PIPELINE_ACTION}」创建并生成。")

    with st.expander(CONTENT_PIPELINE_ACTION, expanded=presentation_id is None):
        render_generate_stage(project_id, include_export=False)

    snapshot = None
    try:
        snapshot = load_project_progress_snapshot()
    except Exception:
        snapshot = None
    ready = bool(snapshot and snapshot.ready_for_export)
    _render_bottom_actions(has_attention=has_attention, ready_for_export=ready)
    render_stage_nav("generate")
