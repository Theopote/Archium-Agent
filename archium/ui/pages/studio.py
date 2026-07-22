"""Presentation Studio — workbench shell (nav | canvas | inspector + bottom dock).

This module is the embeddable workbench. Product navigation must use the
``edit`` stage (``product_flow.PRODUCT_STUDIO_PAGE_KEY``), which calls
``render(embedded=True)``. The standalone ``studio`` page key is a legacy
deep link only and must not be re-added to sidebar navigation.
"""

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
from archium.ui.studio_service import (
    SlideVisualSnapshot,
    StudioPresentationContext,
    get_selected_slide_snapshot,
)
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


_INSPECTOR_TABS = ("属性", "布局", "内容", "AI", "评论", "风格", "检查")


def _select_inspector_tab() -> str:
    """Only the active inspector panel should run work on each rerun."""
    if hasattr(st, "segmented_control"):
        active = st.segmented_control(
            "检查器",
            options=list(_INSPECTOR_TABS),
            key="studio_inspector_tab",
            label_visibility="collapsed",
        )
    else:
        active = st.radio(
            "检查器",
            options=list(_INSPECTOR_TABS),
            horizontal=True,
            key="studio_inspector_tab",
            label_visibility="collapsed",
        )
    if active not in _INSPECTOR_TABS:
        return _INSPECTOR_TABS[0]
    return str(active)


def _render_inspector_tabs(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
    advanced: bool,
    project_id: UUID,
    presentation_id: UUID,
) -> None:
    """Right-column inspector — lazy by active tab (not st.tabs)."""
    from archium.ui.components.chrome import render_inspector_section
    from archium.ui.llm_settings import get_ui_effective_settings
    from archium.ui.studio.scene_repair_prompt_panel import render_deferred_scene_repair_panel

    active = _select_inspector_tab()
    if active == "属性":
        render_inspector_section("属性")
        render_slide_properties(
            slide_snapshot=slide_snapshot,
            advanced=advanced,
            project_id=project_id,
        )
        return
    if active == "布局":
        render_inspector_section("布局")
        render_layout_candidates_panel(slide_snapshot=slide_snapshot, advanced=advanced)
        return
    if active == "内容":
        render_inspector_section("内容")
        render_content_adaptation_panel(slide_snapshot=slide_snapshot)
        return
    if active == "AI":
        render_inspector_section("AI")
        render_ai_workspace(
            slide_snapshot=slide_snapshot,
            presentation_id=presentation_id,
            settings=get_ui_effective_settings(),
        )
        return
    if active == "评论":
        from archium.ui.studio.comment_inbox_panel import render_comment_inbox

        render_inspector_section("评论 Inbox")
        render_comment_inbox(
            presentation_id=presentation_id,
            slide_snapshot=slide_snapshot,
        )
        return
    if active == "风格":
        from archium.ui.studio.deck_theme_panel import render_deck_theme_panel

        render_inspector_section("全稿风格")
        render_deck_theme_panel(
            presentation_id=presentation_id,
            slide_snapshot=slide_snapshot,
        )
        return

    render_inspector_section(
        "检查",
        "自动安全修复可静默应用；其余归入修改建议，需确认。",
    )
    st.markdown("`安全修复 · 可自动应用`　　`AI / QA 修改 · 需确认`")
    render_deferred_scene_repair_panel(slide_snapshot=slide_snapshot)
    st.divider()
    render_inspector_section("人工复核")
    render_human_review_panel(
        presentation_id=presentation_id,
        slide_snapshot=slide_snapshot,
    )


def _render_view_controls(*, compact: bool = False) -> None:
    """Compact view menu instead of a full engineering control row."""
    if "studio_show_nav" not in st.session_state:
        st.session_state.studio_show_nav = True
    if "studio_show_inspector" not in st.session_state:
        st.session_state.studio_show_inspector = True

    show_nav = bool(st.session_state.studio_show_nav)
    show_inspector = bool(st.session_state.studio_show_inspector)
    is_three = show_nav and show_inspector

    with st.popover("视图", use_container_width=True):
        st.checkbox("页面列表", key="studio_show_nav")
        st.checkbox("检查器", key="studio_show_inspector")
        if is_three:
            st.caption("当前：三栏")
            if st.button("画布专注", use_container_width=True, key="studio_canvas_focus"):
                st.session_state.studio_show_nav = False
                st.session_state.studio_show_inspector = False
                st.rerun()
        else:
            st.caption("当前：专注 / 双栏")
            if st.button("恢复三栏", use_container_width=True, key="studio_restore_three"):
                st.session_state.studio_show_nav = True
                st.session_state.studio_show_inspector = True
                st.rerun()
    if not compact:
        bits = []
        if show_nav:
            bits.append("页面列表")
        if show_inspector:
            bits.append("检查器")
        st.caption("视图：" + (" · ".join(bits) if bits else "画布专注"))


def _render_deck_issue_list(*, context: StudioPresentationContext) -> None:
    """Full-deck issue list only — no repair controls (those live in 检查 tab)."""
    from archium.ui.page_status_board_panel import (
        load_page_status_board,
        status_label,
        status_short_detail,
    )

    try:
        board = load_page_status_board(context.presentation.id)
    except Exception:
        st.caption("问题列表暂不可用。")
        return

    attention = [
        row for row in board.rows if row.severity in {"warn", "error"}
    ]
    if not attention:
        st.caption("当前没有需处理的全稿问题。")
        return

    for row in attention:
        title = row.title or f"第 {row.order + 1} 页"
        detail = status_short_detail(row) or status_label(row)
        label = f"第 {row.order + 1} 页 · {title} · {detail}"
        if st.button(
            label,
            key=f"studio_deck_issue_{context.presentation.id}_{row.order}",
            use_container_width=True,
        ):
            if row.slide_id is not None:
                st.session_state.studio_focus_slide_id = str(row.slide_id)
            st.rerun()


def _select_activity_tab(options: list[str], *, key: str) -> str:
    if hasattr(st, "segmented_control"):
        active = st.segmented_control(
            "活动分区",
            options=options,
            key=key,
            label_visibility="collapsed",
        )
    else:
        active = st.radio(
            "活动分区",
            options=options,
            horizontal=True,
            key=key,
            label_visibility="collapsed",
        )
    if active not in options:
        return options[0]
    return str(active)


def _render_studio_info_menus(
    *,
    context: StudioPresentationContext,
    advanced: bool,
    slide_snapshot: SlideVisualSnapshot | None,
    show_progress: bool,
) -> None:
    """Top chrome: one「活动中心」+「视图」— avoids three crowded popovers on small screens.

    - 活动中心 Tabs：状态 / 问题 / 历史
    - 当前页修复操作只在右侧「检查」Tab
    """
    if "studio_show_nav" not in st.session_state:
        st.session_state.studio_show_nav = True
    if "studio_show_inspector" not in st.session_state:
        st.session_state.studio_show_inspector = True

    cols = st.columns([1.35, 1.1, 3.5])
    with cols[0], st.popover("活动中心", use_container_width=True):
        active = _select_activity_tab(
            ["状态", "问题", "历史"],
            key="studio_activity_center_tab",
        )
        if active == "状态":
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
                key_prefix="studio_info_status",
                title="",
            )
        elif active == "问题":
            st.caption("全稿问题列表。点击后聚焦对应页面；修复请用右侧「检查」。")
            _render_deck_issue_list(context=context)
        else:
            render_history_panel(
                context=context,
                advanced=advanced,
                slide_snapshot=slide_snapshot,
            )
    with cols[1]:
        _render_view_controls(compact=True)
    with cols[2]:
        show_nav = bool(st.session_state.get("studio_show_nav", True))
        show_inspector = bool(st.session_state.get("studio_show_inspector", True))
        bits = []
        if show_nav:
            bits.append("页面列表")
        if show_inspector:
            bits.append("检查器")
        st.caption("视图：" + (" · ".join(bits) if bits else "画布专注"))


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
        from archium.ui.components.chrome import render_page_header

        render_page_header("工作室", "页面列表 · 主画布 · 检查器。活动中心与视图在顶部菜单。")

    critics, deck_qa, previews, workflow_output_dir = _workflow_artifacts()
    context = render_studio_selection(
        visual_critic_reports=critics,
        deck_qa_report=deck_qa,
        preview_paths=previews,
        workflow_output_dir=workflow_output_dir,
        compact=embedded,
    )
    if context is None:
        return

    selected_index = int(st.session_state.get("studio_selected_slide_index", 0))
    slide_snapshot = get_selected_slide_snapshot(context, selected_index)
    advanced = bool(st.session_state.get("studio_advanced_mode", False))

    render_studio_toolbar(
        context=context,
        slide_snapshot=slide_snapshot,
        show_export=show_export,
    )
    _render_studio_info_menus(
        context=context,
        advanced=advanced,
        slide_snapshot=slide_snapshot,
        show_progress=show_progress,
    )

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

    slide_snapshot = get_selected_slide_snapshot(context, selected_index)

    with center_col:
        from archium.ui.studio.undo_toolbar import render_undo_toolbar

        render_undo_toolbar(slide_snapshot=slide_snapshot)
        render_slide_canvas(
            slide_snapshot=slide_snapshot,
            advanced=advanced,
            use_interactive_canvas=True,
            project_id=context.project.id,
        )

    if right_col is not None:
        with right_col:
            _render_inspector_tabs(
                slide_snapshot=slide_snapshot,
                advanced=advanced,
                project_id=context.project.id,
                presentation_id=context.presentation.id,
            )
