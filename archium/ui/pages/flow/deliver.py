"""Product-flow stage: 交付."""

from __future__ import annotations

import streamlit as st

from archium.application.visual.visual_workflow_service import VisualWorkflowResult
from archium.ui.app_navigation import get_app_page
from archium.ui.pages.flow import render_stage_header, render_stage_nav
from archium.ui.pages.workspace import render_review_stage
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


def render() -> None:
    render_stage_header("deliver")
    st.info(
        "导出可编辑 PPTX / PDF，并查看质量检查与评审状态。"
        "Benchmark 人工视觉评审可在「设置」中打开。"
    )

    from archium.ui.pages.workspace import ensure_workspace_session

    ensure_workspace_session()
    critics, deck_qa, previews, workflow_output_dir = _workflow_artifacts()
    context = render_studio_selection(
        visual_critic_reports=critics,
        deck_qa_report=deck_qa,
        preview_paths=previews,
        workflow_output_dir=workflow_output_dir,
    )
    if context is not None:
        selected_index = int(st.session_state.get("studio_selected_slide_index", 0))
        slide_snapshot = get_selected_slide_snapshot(context, selected_index)
        st.markdown("#### 导出成果")
        render_export_panel(context=context, slide_snapshot=slide_snapshot)
        project_id = context.project.id
        st.divider()
        st.markdown("#### 质量检查")
        render_review_stage(project_id)
    else:
        st.warning(
            "尚未选择可导出的汇报。请先在「资料」选择项目，并在「生成」或「工作室」中准备页面内容。"
        )
        st.page_link(get_app_page("materials"), label="前往资料", icon="📁")
        st.page_link(get_app_page("generate"), label="前往生成", icon="⚡")

    st.divider()
    st.markdown("#### 人工评审")
    st.caption("30 页 Benchmark 有效视觉评审与可编辑性评审在设置页进行。")
    st.page_link(get_app_page("settings"), label="打开设置 · Benchmark 评审", icon="⚙️")

    st.divider()
    render_stage_nav("deliver")
