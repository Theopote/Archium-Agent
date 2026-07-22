"""Product-flow stage: 交付."""

from __future__ import annotations

import streamlit as st

from archium.application.visual.visual_workflow_service import VisualWorkflowResult
from archium.ui.app_navigation import get_app_page
from archium.ui.pages.flow import render_stage_header, render_stage_nav
from archium.ui.studio.export_panel import render_export_panel
from archium.ui.studio.project_sidebar import render_studio_selection
from archium.ui.studio_service import get_selected_slide_snapshot


def _workflow_artifacts() -> tuple[list[dict] | None, dict | None, list[str] | None, str | None]:
    result = st.session_state.get("last_visual_workflow_result")
    if not isinstance(result, VisualWorkflowResult):
        return None, None, None, None
    deck_qa = result.deck_qa_report if isinstance(result.deck_qa_report, dict) else None
    critics = list(result.visual_critic_reports or [])
    previews = list(result.render_paths or [])
    output_dir = result.workflow_run.state.get("output_dir")
    return critics, deck_qa, previews, output_dir if isinstance(output_dir, str) else None


def _render_readiness(context: object) -> None:
    st.markdown("#### 交付准备度")
    ready = bool(getattr(context, "ready_for_export", False))
    slide_count = int(getattr(context, "slide_count", 0) or 0)
    layout_ready = int(getattr(context, "layout_ready_count", 0) or 0)
    pending = max(0, slide_count - layout_ready)

    warn_count = 0
    blocker_count = 0
    deck_qa = st.session_state.get("last_visual_workflow_result")
    if isinstance(deck_qa, VisualWorkflowResult) and isinstance(deck_qa.deck_qa_report, dict):
        warn_count = int(deck_qa.deck_qa_report.get("warning_count") or 0)
        blocker_count = int(deck_qa.deck_qa_report.get("blocker_count") or 0)

    cols = st.columns(4)
    cols[0].metric("PPTX", "可导出" if ready else "版式未齐")
    cols[1].metric("PDF", "可导出" if ready else "版式未齐")
    cols[2].metric("仍有警告页", pending if pending else warn_count)
    cols[3].metric("Blocker", blocker_count)


def _render_delivery_records() -> None:
    st.markdown("#### 交付记录")
    records = list(st.session_state.get("delivery_export_records") or [])
    if not records:
        st.caption("尚无导出记录。完成导出后会显示版本、时间与路径。")
        return
    for item in reversed(records[-8:]):
        st.markdown(
            f"- **{item.get('format', '文件')}** · {item.get('when', '')}"
            f" · `{item.get('path', '')}`"
        )


def render() -> None:
    render_stage_header("deliver")
    st.info("检查准备度并导出可编辑成果。研发验收工具在「设置 → 开发者与验收」。")

    from archium.ui.pages.workspace import ensure_workspace_session

    ensure_workspace_session()
    critics, deck_qa, previews, workflow_output_dir = _workflow_artifacts()
    context = render_studio_selection(
        visual_critic_reports=critics,
        deck_qa_report=deck_qa,
        preview_paths=previews,
        workflow_output_dir=workflow_output_dir,
    )
    if context is None:
        st.warning(
            "尚未选择可导出的汇报。请先在「资料」选择项目，并在「生成」或「工作室」中准备页面内容。"
        )
        from archium.ui import icons

        st.page_link(get_app_page("materials"), label="前往资料", icon=icons.MATERIALS)
        st.page_link(get_app_page("generate"), label="前往生成", icon=icons.GENERATE)
        render_stage_nav("deliver")
        return

    _render_readiness(context)
    st.divider()

    selected_index = int(st.session_state.get("studio_selected_slide_index", 0))
    slide_snapshot = get_selected_slide_snapshot(context, selected_index)
    st.markdown("#### 导出配置")
    st.caption("选择格式并导出。完整文件路径会写入下方交付记录。")
    render_export_panel(context=context, slide_snapshot=slide_snapshot)

    st.divider()
    _render_delivery_records()

    with st.expander("质量检查（可选）", expanded=False):
        from archium.ui.pages.workspace import render_review_stage

        render_review_stage(context.project.id)

    st.divider()
    render_stage_nav("deliver")
