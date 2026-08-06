"""Product-flow stage: 生成 — page queue + recovery CTAs."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.unit_of_work import unit_of_work
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


def _handle_batch_retry_failed(presentation_id: UUID) -> None:
    """处理批量重试失败页面。"""
    from archium.application.batch_operations import PresentationBatchOperations
    from archium.ui.components.enhanced_ui import render_status_indicator

    with st.spinner("正在批量重试失败页面..."):
        try:
            with unit_of_work() as uow:
                batch_ops = PresentationBatchOperations(uow)
                result = batch_ops.batch_retry_failed_slides(
                    presentation_id,
                    continue_on_error=True,
                )

            # 显示结果
            if result.all_succeeded:
                st.success(f"✅ 全部重试成功！共处理 {result.success_count} 页")
            elif result.any_succeeded:
                st.warning(
                    f"⚠️ 部分成功：{result.success_count} 成功，{result.failure_count} 失败"
                )
                if result.failed_items:
                    with st.expander("查看失败详情", expanded=False):
                        for item, error in result.failed_items:
                            st.text(f"页面 {item}: {str(error)[:100]}")
            else:
                st.error(f"❌ 批量重试失败：{result.failure_count} 页全部失败")

            # 显示警告
            for warning in result.warnings:
                st.warning(warning)

            # 刷新页面
            if result.any_succeeded:
                st.rerun()

        except Exception as e:
            from archium.ui.components.enhanced_ui import render_error_message

            render_error_message(
                e,
                title="批量重试失败",
                action_label="重试",
                on_action=lambda: _handle_batch_retry_failed(presentation_id),
            )


def _handle_skip_failed_slides(presentation_id: UUID) -> None:
    """处理跳过失败页面。"""
    from archium.application.batch_operations import PresentationBatchOperations

    # 确认对话框
    with st.container():
        st.warning("⚠️ 确定要跳过所有失败页面吗？")
        st.caption("这将标记失败页面为已跳过，继续处理其他页面。此操作可以撤销。")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("确认跳过", key="confirm_skip_failed", type="primary", use_container_width=True):
                with st.spinner("正在跳过失败页面..."):
                    try:
                        with unit_of_work() as uow:
                            batch_ops = PresentationBatchOperations(uow)
                            # 获取失败页面ID并标记为跳过
                            failed_slides = batch_ops._get_failed_slides(presentation_id)
                            slide_ids = [slide.id for slide in failed_slides]

                            if slide_ids:
                                result = batch_ops.batch_update_slide_property(
                                    slide_ids,
                                    "generation_status",
                                    "skipped",
                                )
                                st.success(f"✅ 已跳过 {result.success_count} 个失败页面")
                                st.rerun()
                            else:
                                st.info("没有失败页面需要跳过")

                    except Exception as e:
                        st.error(f"跳过失败：{str(e)}")

        with col2:
            if st.button("取消", key="cancel_skip_failed", use_container_width=True):
                st.rerun()


def _selected_presentation_id(project_id: UUID) -> UUID | None:
    selected = st.session_state.get("selected_presentation_id")
    with unit_of_work() as uow:
        session = uow
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
        with unit_of_work() as uow:
            context = build_project_context(uow, project_id)
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
            with unit_of_work() as uow:
                session = uow
                dispatch_next_best_action(
                    session,
                    as_session_state(st.session_state),
                    readiness.suggested_action,
                    project_id=project_id,
                    settings=settings,
                )


def _render_queue_summary(metrics: GenerateQueueMetrics) -> None:
    from archium.ui.components.enhanced_ui import render_quick_stats, render_progress_card

    # 显示进度条
    render_progress_card(
        title="页面生成进度",
        current=metrics.complete,
        total=metrics.total,
        details=f"待处理 {metrics.pending} · 失败 {metrics.failed}",
        show_percentage=True,
    )

    st.markdown("")


def _render_page_queue(project_id: UUID, presentation_id: UUID) -> bool:
    """Return True when any attention rows exist."""
    from archium.ui.components.enhanced_ui import render_status_indicator

    board = load_page_status_board(presentation_id)
    metrics = metrics_from_board(board)
    _render_queue_summary(metrics)

    if not board.rows:
        st.info(f"尚未生成页面。展开下方「{CONTENT_PIPELINE_ACTION}」开始生成。")
        return False

    # 批量操作栏
    if metrics.failed > 0:
        st.markdown("#### 批量操作")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🔄 重试全部失败页", key="retry_all_failed", use_container_width=True):
                _handle_batch_retry_failed(presentation_id)
        with col2:
            if st.button("⏭️ 跳过失败继续", key="skip_failed", use_container_width=True):
                _handle_skip_failed_slides(presentation_id)

    st.markdown("#### 逐页队列")

    # 按状态分组显示
    completed_rows = []
    pending_rows = []
    failed_rows = []

    for row in board.rows:
        if row.severity in {"warn", "error"}:
            failed_rows.append(row)
        elif "完成" in queue_row_status(row):
            completed_rows.append(row)
        else:
            pending_rows.append(row)

    has_attention = len(failed_rows) > 0

    # 显示失败页面（优先）
    if failed_rows:
        st.markdown("**❌ 需要处理（{}）**".format(len(failed_rows)))
        for row in failed_rows:
            _render_queue_row(row, project_id, presentation_id, show_actions=True)
        st.markdown("")

    # 显示待处理页面
    if pending_rows:
        with st.expander(f"⏳ 待生成（{len(pending_rows)}）", expanded=len(failed_rows) == 0):
            for row in pending_rows:
                _render_queue_row(row, project_id, presentation_id, show_actions=False)

    # 显示已完成页面
    if completed_rows:
        with st.expander(f"✅ 已完成（{len(completed_rows)}）", expanded=False):
            for row in completed_rows:
                _render_queue_row(row, project_id, presentation_id, show_actions=False)

    return has_attention


def _render_queue_row(row, project_id: UUID, presentation_id: UUID, show_actions: bool) -> None:
    """渲染单个队列行"""
    from archium.ui.components.enhanced_ui import render_status_indicator

    status_text = queue_row_status(row)
    title = (row.title or f"第 {row.order + 1} 页").strip()

    # 确定状态类型
    if row.severity == "error":
        status_type = "error"
    elif row.severity == "warn":
        status_type = "warning"
    elif "完成" in status_text:
        status_type = "success"
    elif "进行" in status_text:
        status_type = "pending"
    else:
        status_type = "info"

    cols = st.columns([0.5, 3, 1.5, 1])

    with cols[0]:
        st.markdown(f"`{row.order + 1:02d}`")

    with cols[1]:
        st.markdown(f"**{title}**")
        if row.detail and row.severity in {"warn", "error"}:
            st.caption(f"⚠️ {row.detail}")

    with cols[2]:
        render_status_indicator(status_type, status_text, size="small")

    with cols[3]:
        if show_actions:
            render_compact_page_actions(
                presentation_id=presentation_id,
                project_id=project_id,
                row=row,
                key_prefix="generate_queue",
            )


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

    with unit_of_work() as uow:
        starter = get_genesis_starter_state(uow, project_id)
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
    from archium.ui.components.navigation import (
        render_workflow_progress_indicator,
        render_stage_navigation_hint,
        set_current_stage,
    )

    # 设置当前阶段
    set_current_stage("generate")

    # 显示五阶段进度
    render_workflow_progress_indicator("generate")

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
            # 显示下一步提示
            if not has_attention:
                render_stage_navigation_hint("generate")
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
