"""Presentation Studio — three-column editing shell."""

from __future__ import annotations

import streamlit as st

from archium.application.visual.visual_workflow_service import VisualWorkflowResult
from archium.ui.studio.ai_edit_panel import render_ai_edit_panel
from archium.ui.studio.export_panel import render_export_panel
from archium.ui.studio.history_panel import render_history_panel
from archium.ui.studio.project_sidebar import render_studio_selection
from archium.ui.studio.slide_canvas import render_slide_canvas
from archium.ui.studio.slide_navigator import render_slide_navigator
from archium.ui.studio.slide_properties import render_slide_properties
from archium.ui.studio_service import get_selected_slide_snapshot
from archium.ui.workflow_progress_panel import render_workflow_progress_panel


def _workflow_artifacts() -> tuple[list[dict] | None, dict | None, list[str] | None]:
    result = st.session_state.get("last_visual_workflow_result")
    if not isinstance(result, VisualWorkflowResult):
        return None, None, None
    deck_qa = result.deck_qa_report if isinstance(result.deck_qa_report, dict) else None
    critics = list(result.visual_critic_reports or [])
    previews = list(result.render_paths or [])
    return critics, deck_qa, previews


def _apply_visual_result(result: object) -> None:
    if isinstance(result, VisualWorkflowResult):
        st.session_state.last_visual_workflow_result = result
        st.session_state.visual_workflow_run_id = str(result.workflow_run.id)


def render() -> None:
    st.markdown("### 汇报工作室")
    st.caption(
        "在同一界面浏览页面、查看版式属性并导出成果。"
        "高级模式可显示 SlideSpec / LayoutPlan 等技术术语。"
    )

    critics, deck_qa, previews = _workflow_artifacts()
    context = render_studio_selection(
        visual_critic_reports=critics,
        deck_qa_report=deck_qa,
        preview_paths=previews,
    )
    if context is None:
        return

    render_export_panel(context=context)
    st.divider()

    left_col, center_col, right_col = st.columns([1.05, 2.1, 1.05], gap="medium")

    with left_col:
        selected_index = render_slide_navigator(context=context)

    advanced = bool(st.session_state.get("studio_advanced_mode", False))
    slide_snapshot = get_selected_slide_snapshot(context, selected_index)

    with center_col:
        render_slide_canvas(slide_snapshot=slide_snapshot, advanced=advanced)

    with right_col:
        render_slide_properties(slide_snapshot=slide_snapshot, advanced=advanced)
        st.divider()
        render_ai_edit_panel(disabled=True)

    st.divider()
    render_history_panel(context=context, advanced=advanced)

    render_workflow_progress_panel(
        context.project.id,
        scope="visual",
        presentation_id=context.presentation.id,
        result_session_key="last_visual_workflow_result",
        on_complete=_apply_visual_result,
        rerun_on_complete=False,
    )
