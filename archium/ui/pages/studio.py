"""Presentation Studio — three-column editing shell."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.visual.visual_workflow_service import VisualWorkflowResult
from archium.ui.studio.ai_edit_panel import render_ai_edit_panel
from archium.ui.studio.content_adaptation_panel import render_content_adaptation_panel
from archium.ui.studio.export_panel import render_studio_toolbar
from archium.ui.studio.history_panel import render_history_panel
from archium.ui.studio.human_review_panel import render_human_review_panel
from archium.ui.studio.layout_candidates_panel import render_layout_candidates_panel
from archium.ui.studio.project_sidebar import render_studio_selection
from archium.ui.studio.slide_canvas_enhanced import render_slide_canvas
from archium.ui.studio.slide_navigator import render_slide_navigator
from archium.ui.studio.slide_properties import render_slide_properties
from archium.ui.studio_service import SlideVisualSnapshot, get_selected_slide_snapshot
from archium.ui.workflow_progress_panel import render_workflow_progress_panel


def _workflow_artifacts() -> tuple[list[dict] | None, dict | None, list[str] | None, str | None]:
    result = st.session_state.get("last_visual_workflow_result")
    if not isinstance(result, VisualWorkflowResult):
        return None, None, None, None
    deck_qa = result.deck_qa_report if isinstance(result.deck_qa_report, dict) else None
    critics = list(result.visual_critic_reports or [])
    previews = list(result.render_paths or [])
    output_dir = result.workflow_run.state.get("output_dir")
    return critics, deck_qa, previews, output_dir if isinstance(output_dir, str) else None


def _apply_visual_result(result: object) -> None:
    if isinstance(result, VisualWorkflowResult):
        st.session_state.last_visual_workflow_result = result
        st.session_state.visual_workflow_run_id = str(result.workflow_run.id)


def _render_inspector_tabs(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
    advanced: bool,
    project_id: UUID,
    presentation_id: UUID,
) -> None:
    """Right-column inspector: one job per tab; AI edit sits with Before/After."""
    from archium.ui.llm_settings import get_ui_effective_settings
    from archium.ui.studio.proposal_compare_panel import render_proposal_compare_panel
    from archium.ui.studio.scene_repair_prompt_panel import render_deferred_scene_repair_panel

    tab_props, tab_layout, tab_content, tab_ai, tab_check = st.tabs(
        ["属性", "布局", "内容", "AI", "检查"]
    )

    with tab_props:
        render_slide_properties(
            slide_snapshot=slide_snapshot,
            advanced=advanced,
            project_id=project_id,
        )

    with tab_layout:
        render_layout_candidates_panel(slide_snapshot=slide_snapshot, advanced=advanced)

    with tab_content:
        render_content_adaptation_panel(slide_snapshot=slide_snapshot)

    with tab_ai:
        render_ai_edit_panel(
            slide_snapshot=slide_snapshot,
            presentation_id=presentation_id,
        )
        st.divider()
        render_proposal_compare_panel(
            slide_snapshot=slide_snapshot,
            presentation_id=presentation_id,
            settings=get_ui_effective_settings(),
        )

    with tab_check:
        render_deferred_scene_repair_panel(slide_snapshot=slide_snapshot)
        render_human_review_panel(
            presentation_id=presentation_id,
            slide_snapshot=slide_snapshot,
        )


def render(
    *,
    embedded: bool = False,
    show_header: bool | None = None,
    show_export: bool | None = None,
    show_progress: bool | None = None,
) -> None:
    """Render the presentation studio shell.

    When embedded in the product-flow「工作室」stage, pass ``embedded=True``
    (or ``show_header=False``) so the outer stage chrome owns the page title.
    ``show_export`` controls the compact export popover vs a link to「交付」;
    the full export panel lives on the deliver stage.
    """
    if show_header is None:
        show_header = not embedded
    if show_export is None:
        show_export = not embedded
    if show_progress is None:
        show_progress = not embedded

    if show_header:
        st.markdown("### 工作室")
        st.caption(
            "在同一界面浏览页面、调整版式与图文。"
            "完整导出在「交付」；此处「导出」为快捷入口。"
            "高级模式可显示 SlideSpec / LayoutPlan 等技术术语。"
        )

    critics, deck_qa, previews, workflow_output_dir = _workflow_artifacts()
    context = render_studio_selection(
        visual_critic_reports=critics,
        deck_qa_report=deck_qa,
        preview_paths=previews,
        workflow_output_dir=workflow_output_dir,
    )
    if context is None:
        return

    from archium.ui.page_status_board_panel import render_page_status_board

    with st.expander("逐页状态板", expanded=False):
        render_page_status_board(
            presentation_id=context.presentation.id,
            project_id=context.project.id,
            compact=False,
            key_prefix=f"studio_page_status_{context.presentation.id}",
        )

    selected_index = int(st.session_state.get("studio_selected_slide_index", 0))
    slide_snapshot = get_selected_slide_snapshot(context, selected_index)

    # Editing chrome first; export is a secondary popover (or link to 交付).
    render_studio_toolbar(
        context=context,
        slide_snapshot=slide_snapshot,
        show_export=show_export,
    )
    st.divider()

    left_col, center_col, right_col = st.columns([1.05, 2.1, 1.05], gap="medium")

    with left_col:
        selected_index = render_slide_navigator(context=context)

    advanced = bool(st.session_state.get("studio_advanced_mode", False))
    slide_snapshot = get_selected_slide_snapshot(context, selected_index)

    with center_col:
        from archium.ui.studio.undo_toolbar import render_undo_toolbar

        render_undo_toolbar(slide_snapshot=slide_snapshot)
        render_slide_canvas(
            slide_snapshot=slide_snapshot,
            advanced=advanced,
            use_interactive_canvas=True,
        )

    with right_col:
        _render_inspector_tabs(
            slide_snapshot=slide_snapshot,
            advanced=advanced,
            project_id=context.project.id,
            presentation_id=context.presentation.id,
        )

    st.divider()
    render_history_panel(context=context, advanced=advanced, slide_snapshot=slide_snapshot)

    if show_progress:
        render_workflow_progress_panel(
            context.project.id,
            scope="visual",
            presentation_id=context.presentation.id,
            result_session_key="last_visual_workflow_result",
            on_complete=_apply_visual_result,
            rerun_on_complete=False,
        )
