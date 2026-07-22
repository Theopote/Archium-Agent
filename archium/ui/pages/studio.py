"""Presentation Studio — workbench shell (nav | canvas | inspector + bottom dock)."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.visual.visual_workflow_service import VisualWorkflowResult
from archium.ui.studio.ai_workspace_panel import render_ai_workspace
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
    """Right-column inspector tabs."""
    from archium.ui.llm_settings import get_ui_effective_settings
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
        render_ai_workspace(
            slide_snapshot=slide_snapshot,
            presentation_id=presentation_id,
            settings=get_ui_effective_settings(),
        )

    with tab_check:
        st.markdown("**检查**")
        st.caption(
            "自动安全修复（越界 / contain / 缺省 / 无损对齐）可静默应用；"
            "其余归入修改建议，需确认。"
        )
        st.markdown("`安全修复 · 可自动应用`　　`AI / QA 修改 · 需确认`")
        render_deferred_scene_repair_panel(slide_snapshot=slide_snapshot)
        st.divider()
        st.markdown("**人工复核**")
        render_human_review_panel(
            presentation_id=presentation_id,
            slide_snapshot=slide_snapshot,
        )


def _render_bottom_dock(
    *,
    context: object,
    advanced: bool,
    slide_snapshot: SlideVisualSnapshot | None,
    show_progress: bool,
) -> None:
    """Collapsible dock: 状态 / 问题 / 历史."""
    with st.expander("状态 / 问题 / 历史", expanded=False):
        dock_tabs = st.tabs(["状态", "问题", "历史"])
        with dock_tabs[0]:
            if show_progress:
                render_workflow_progress_panel(
                    context.project.id,
                    scope="visual",
                    presentation_id=context.presentation.id,
                    result_session_key="last_visual_workflow_result",
                    on_complete=_apply_visual_result,
                    rerun_on_complete=False,
                )
            else:
                st.caption("生成进度在后台任务运行时显示。")
            from archium.ui.page_status_board_panel import render_page_status_board

            render_page_status_board(
                presentation_id=context.presentation.id,
                project_id=context.project.id,
                compact=True,
                key_prefix="studio_dock_status",
                title="",
            )
        with dock_tabs[1]:
            from archium.ui.studio.human_review_panel import render_human_review_panel
            from archium.ui.studio.scene_repair_prompt_panel import (
                render_deferred_scene_repair_panel,
            )

            st.caption("安全修复与需确认问题。")
            render_deferred_scene_repair_panel(slide_snapshot=slide_snapshot)
            render_human_review_panel(
                presentation_id=context.presentation.id,
                slide_snapshot=slide_snapshot,
            )
        with dock_tabs[2]:
            render_history_panel(
                context=context,
                advanced=advanced,
                slide_snapshot=slide_snapshot,
            )

def render(
    *,
    embedded: bool = False,
    show_header: bool | None = None,
    show_export: bool | None = None,
    show_progress: bool | None = None,
) -> None:
    """Render the presentation studio workbench."""
    if show_header is None:
        show_header = not embedded
    if show_export is None:
        show_export = not embedded
    if show_progress is None:
        show_progress = not embedded

    if show_header:
        st.markdown("### 工作室")
        st.caption("页面列表 · 主画布 · 属性/布局/AI。历史与生成状态收在底部 Dock。")

    critics, deck_qa, previews, workflow_output_dir = _workflow_artifacts()
    context = render_studio_selection(
        visual_critic_reports=critics,
        deck_qa_report=deck_qa,
        preview_paths=previews,
        workflow_output_dir=workflow_output_dir,
    )
    if context is None:
        return

    selected_index = int(st.session_state.get("studio_selected_slide_index", 0))
    slide_snapshot = get_selected_slide_snapshot(context, selected_index)

    render_studio_toolbar(
        context=context,
        slide_snapshot=slide_snapshot,
        show_export=show_export,
    )

    layout_cols = st.columns([1, 1, 1, 1.2])
    if "studio_show_nav" not in st.session_state:
        st.session_state.studio_show_nav = True
    if "studio_show_inspector" not in st.session_state:
        st.session_state.studio_show_inspector = True
    with layout_cols[0]:
        st.toggle("页面列表", key="studio_show_nav")
    with layout_cols[1]:
        st.toggle("检查器", key="studio_show_inspector")
    with layout_cols[2]:
        if st.button("画布最大化", use_container_width=True, key="studio_canvas_maximize"):
            st.session_state.studio_show_nav = False
            st.session_state.studio_show_inspector = False
            st.rerun()
    with layout_cols[3]:
        if st.button("恢复三栏", use_container_width=True, key="studio_restore_three"):
            st.session_state.studio_show_nav = True
            st.session_state.studio_show_inspector = True
            st.rerun()

    show_nav = bool(st.session_state.studio_show_nav)
    show_inspector = bool(st.session_state.studio_show_inspector)
    if show_nav and show_inspector:
        left_col, center_col, right_col = st.columns([1.05, 2.1, 1.05], gap="medium")
    elif show_nav and not show_inspector:
        left_col, center_col = st.columns([1.1, 2.9], gap="medium")
        right_col = None
    elif show_inspector and not show_nav:
        center_col, right_col = st.columns([2.9, 1.1], gap="medium")
        left_col = None
    else:
        center_col = st.container()
        left_col = None
        right_col = None

    if left_col is not None:
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

    if right_col is not None:
        with right_col:
            _render_inspector_tabs(
                slide_snapshot=slide_snapshot,
                advanced=advanced,
                project_id=context.project.id,
                presentation_id=context.presentation.id,
            )

    _render_bottom_dock(
        context=context,
        advanced=advanced,
        slide_snapshot=slide_snapshot,
        show_progress=show_progress,
    )
