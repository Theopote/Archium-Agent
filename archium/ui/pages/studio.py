"""Presentation Studio — workbench shell (nav | canvas | inspector).

This module is the embeddable workbench. Product navigation must use the
``edit`` stage (``product_flow.PRODUCT_STUDIO_PAGE_KEY``), which calls
``render(embedded=True)``. The standalone ``studio`` URL redirects to ``edit``.
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
from archium.ui.studio.storyline_navigator import (
    load_studio_narrative,
    render_storyline_navigator,
)
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


def _render_art_direction_gate_if_paused() -> None:
    """Surface ArtDirection review when a visual job pauses at that gate."""
    result = st.session_state.get("last_visual_workflow_result")
    if not isinstance(result, VisualWorkflowResult):
        return
    if not result.awaiting_review or result.review_gate != "art_direction":
        return
    if result.art_direction is None:
        return
    from archium.ui.art_direction_panel import render_art_direction_panel

    render_art_direction_panel(
        art_direction=result.art_direction,
        workflow_run_id=result.workflow_run.id,
        awaiting_approval=True,
    )


def _render_studio_art_direction(*, project_id: UUID, presentation_id: UUID) -> None:
    """Editable 汇报气质 on the Style tab (not only when the gate pauses)."""
    from archium.application.api.session import api_from_session
    from archium.infrastructure.database.session import get_session
    from archium.ui.art_direction_panel import render_art_direction_panel

    result = st.session_state.get("last_visual_workflow_result")
    art = None
    workflow_run_id = None
    awaiting = False
    if isinstance(result, VisualWorkflowResult) and result.art_direction is not None:
        art = result.art_direction
        if result.awaiting_review and result.review_gate == "art_direction":
            awaiting = True
            workflow_run_id = result.workflow_run.id

    if art is None:
        with get_session() as session:
            art = api_from_session(session).visual.resolve_art_direction_for_presentation(
                project_id=project_id,
                presentation_id=presentation_id,
            )

    if art is None:
        st.caption("尚无汇报气质。生成页时完成视觉编排后会出现在这里。")
        return
    render_art_direction_panel(
        art_direction=art,
        workflow_run_id=workflow_run_id,
        awaiting_approval=awaiting,
    )


def _render_design_system_panel(
    *,
    project_id: UUID,
    presentation_id: UUID,
    slide_snapshot: SlideVisualSnapshot | None,
) -> None:
    """Render the professional design system panel in Studio."""
    from archium.infrastructure.database.session import get_session
    from archium.application.design_system_integration import DesignSystemIntegrationService
    
    st.markdown("### 🎨 专业设计系统")
    st.caption("应用专业模板、优化布局、评估设计质量")
    
    with get_session() as session:
        design_system_service = DesignSystemIntegrationService(session)
    
    # Template selection
    st.markdown("#### 📋 模板选择")
    available_templates = design_system_service.get_available_templates()
    
    if available_templates:
        template_options = {t["id"]: f"{t['name']} - {t['type']}" for t in available_templates}
        selected_template = st.selectbox(
            "选择专业模板",
            options=list(template_options.keys()),
            format_func=lambda x: template_options.get(x, x),
            key="studio_template_select",
        )
        
        if st.button("应用模板", key="apply_template_btn"):
            try:
                template_result = design_system_service.apply_template_to_presentation(
                    presentation_id,
                    selected_template,
                    {"title": "演示文稿", "slides_count": 1},
                )
                st.success(f"已应用模板: {template_result['template_name']}")
            except Exception as e:
                st.error(f"应用模板失败: {str(e)}")
    else:
        st.info("暂无可用模板")
    
    st.divider()
    
    # Intelligent layout optimization
    st.markdown("#### 🧠 智能布局优化")
    
    if slide_snapshot and slide_snapshot.slide:
        if st.button("优化当前幻灯片布局", key="optimize_layout_btn"):
            try:
                slide_data = {
                    "id": str(slide_snapshot.slide.id),
                    "title": slide_snapshot.slide.title,
                    "body": slide_snapshot.slide.body,
                }
                
                layout_result = design_system_service.optimize_slide_layout(slide_data)
                
                st.success(f"推荐布局: {layout_result['recommended_layout']}")
                st.metric("布局评分", f"{layout_result['layout_score']:.1f}/100")
                
                with st.expander("布局详情"):
                    st.json(layout_result["layout_details"])
            except Exception as e:
                st.error(f"布局优化失败: {str(e)}")
    else:
        st.info("请先选择幻灯片以进行布局优化")
    
    st.divider()
    
    # Design quality assessment
    st.markdown("#### 📊 设计质量评估")
    
    if st.button("评估当前幻灯片质量", key="assess_quality_btn"):
        if slide_snapshot and slide_snapshot.slide:
            try:
                slide_data = [{
                    "id": str(slide_snapshot.slide.id),
                    "title": slide_snapshot.slide.title,
                    "body": slide_snapshot.slide.body,
                }]
                
                quality_result = design_system_service.assess_presentation_quality(
                    presentation_id,
                    slide_data,
                )
                
                summary = quality_result["summary"]
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("总体评分", f"{summary['average_score']}/100")
                with col2:
                    st.metric("质量等级", summary['overall_level'].upper())
                with col3:
                    needs_review = len(summary.get('needs_review', []))
                    st.metric("需要改进", needs_review)
                
                if summary.get('priority_improvements'):
                    st.markdown("**优先改进建议:**")
                    for i, improvement in enumerate(summary['priority_improvements'][:3], 1):
                        st.markdown(f"{i}. {improvement}")
            except Exception as e:
                st.error(f"质量评估失败: {str(e)}")
        else:
            st.warning("请先选择幻灯片以进行质量评估")
    
    st.divider()
    
    # Visual elements library
    st.markdown("#### 🎨 视觉元素库")
    
    search_query = st.text_input("搜索图标、图表等", key="visual_elements_search")
    
    if search_query:
        try:
            results = design_system_service.search_visual_elements(search_query)
            if results:
                st.markdown(f"找到 {len(results)} 个元素")
                for element in results[:5]:
                    with st.container():
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.markdown("🎨")
                        with col2:
                            st.markdown(f"**{element['name']}**")
                            st.caption(f"{element['type']} - {element.get('description', '')}")
            else:
                st.info("未找到匹配元素")
        except Exception as e:
            st.error(f"搜索失败: {str(e)}")


_INSPECTOR_TABS = ("属性", "布局", "内容", "修改", "评论", "风格", "设计系统", "检查")


def _select_inspector_tab() -> str:
    """Only the active inspector panel should run work on each rerun."""
    # Widget key must differ from logical ``studio_inspector_tab`` so code can
    # open the「修改」tab without StreamlitAPIException.
    logical = "studio_inspector_tab"
    widget = "studio_ui_inspector_tab"
    if logical not in st.session_state:
        st.session_state[logical] = _INSPECTOR_TABS[0]
    desired = st.session_state[logical]
    if desired not in _INSPECTOR_TABS:
        desired = _INSPECTOR_TABS[0]
        st.session_state[logical] = desired
    st.session_state[widget] = desired
    if hasattr(st, "segmented_control"):
        active = st.segmented_control(
            "检查器",
            options=list(_INSPECTOR_TABS),
            key=widget,
            label_visibility="collapsed",
        )
    else:
        active = st.radio(
            "检查器",
            options=list(_INSPECTOR_TABS),
            horizontal=True,
            key=widget,
            label_visibility="collapsed",
        )
    if active not in _INSPECTOR_TABS:
        active = _INSPECTOR_TABS[0]
    st.session_state[logical] = str(active)
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
    if active == "修改":
        render_inspector_section("修改与提案")
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

        render_inspector_section("汇报气质")
        _render_studio_art_direction(project_id=project_id, presentation_id=presentation_id)
        st.divider()
        render_inspector_section("全稿风格")
        render_deck_theme_panel(
            presentation_id=presentation_id,
        )
        return
    if active == "设计系统":
        render_inspector_section("专业设计系统")
        _render_design_system_panel(
            project_id=project_id,
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
    if "studio_center_mode" not in st.session_state:
        st.session_state.studio_center_mode = "edit"

    # Widget keys ≠ logical flags so assistants can toggle panes safely.
    st.session_state["studio_ui_center_mode"] = str(
        st.session_state.get("studio_center_mode", "edit")
    )
    st.session_state["studio_ui_show_nav"] = bool(st.session_state.studio_show_nav)
    st.session_state["studio_ui_show_inspector"] = bool(
        st.session_state.studio_show_inspector
    )

    with st.popover("视图", width="stretch"):
        st.radio(
            "中心区域",
            options=["edit", "overview"],
            format_func=lambda value: "单页编辑" if value == "edit" else "全稿鸟瞰",
            key="studio_ui_center_mode",
            horizontal=True,
        )
        st.checkbox("页面列表", key="studio_ui_show_nav")
        st.checkbox("设计助理", key="studio_ui_show_inspector")
        st.session_state.studio_center_mode = str(
            st.session_state.get("studio_ui_center_mode", "edit")
        )
        st.session_state.studio_show_nav = bool(
            st.session_state.get("studio_ui_show_nav", True)
        )
        st.session_state.studio_show_inspector = bool(
            st.session_state.get("studio_ui_show_inspector", True)
        )
        show_nav = bool(st.session_state.studio_show_nav)
        show_inspector = bool(st.session_state.studio_show_inspector)
        is_three = show_nav and show_inspector
        if is_three:
            st.caption("当前：三栏")
            if st.button("画布专注", width="stretch", key="studio_canvas_focus"):
                st.session_state.studio_show_nav = False
                st.session_state.studio_show_inspector = False
                st.rerun()
        else:
            st.caption("当前：专注 / 双栏")
            if st.button("恢复三栏", width="stretch", key="studio_restore_three"):
                st.session_state.studio_show_nav = True
                st.session_state.studio_show_inspector = True
                st.rerun()

    show_nav = bool(st.session_state.studio_show_nav)
    show_inspector = bool(st.session_state.studio_show_inspector)
    center_mode = str(st.session_state.get("studio_center_mode", "edit"))
    if not compact:
        bits = []
        if center_mode == "overview":
            bits.append("全稿鸟瞰")
        else:
            bits.append("单页编辑")
        if show_nav:
            bits.append("页面列表")
        if show_inspector:
            bits.append("设计助理")
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
            width="stretch",
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
    with cols[0], st.popover("活动中心", width="stretch"):
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
            _render_art_direction_gate_if_paused()
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
            bits.append("设计助理")
        st.caption("视图：" + (" · ".join(bits) if bits else "画布专注"))


def _render_studio_partner_strip(context: StudioPresentationContext) -> None:
    """Thin partner chrome: understanding + storyline thesis (not a feature dashboard)."""
    try:
        from archium.ui.project_knowledge_profile import render_ai_understanding_panel
        from archium.ui.studio.storyline_navigator import load_studio_narrative
        from archium.ui.studio_service import studio_readiness_label

        left, right = st.columns([2.4, 1])
        with left:
            render_ai_understanding_panel(
                context.project.id,
                compact=True,
                show_actions=False,
                key_prefix=f"studio_understand_{context.project.id}",
                title="项目理解",
            )
            narrative = load_studio_narrative(context.presentation.id)
            if narrative.thesis:
                st.caption(f"故事线论点：{narrative.thesis[:160]}")
        with right:
            st.caption(studio_readiness_label(context))
            st.caption("工作台：故事线 · 页面 · 设计助理")
            action_cols = st.columns(2)
            with action_cols[0]:
                if st.button(
                    "全稿鸟瞰",
                    key=f"studio_partner_overview_{context.presentation.id}",
                    width="stretch",
                ):
                    from archium.ui.studio.studio_pending_state import request_center_mode

                    request_center_mode("overview")
                    st.rerun()
            with action_cols[1]:
                if st.button(
                    "聚焦本页建议",
                    key=f"studio_open_ai_{context.presentation.id}",
                    width="stretch",
                ):
                    from archium.ui.studio.studio_pending_state import (
                        request_show_inspector,
                        request_show_nav,
                    )

                    request_show_inspector(show=True)
                    request_show_nav(show=True)
                    st.session_state.studio_inspector_expanded = False
                    st.rerun()
    except Exception:
        return


def _render_wireframe_mode_banner(context: StudioPresentationContext) -> None:
    """Inform user when deck is still in genesis wireframe preview mode."""
    try:
        from archium.application.genesis_starter_service import (
            get_genesis_starter_state,
            presentation_has_formal_visual_previews,
        )
        from archium.infrastructure.database.session import get_session
        from archium.ui.app_navigation import get_app_page

        with get_session() as session:
            starter = get_genesis_starter_state(session, context.project.id)
            if starter is None:
                return
            if presentation_has_formal_visual_previews(session, starter.presentation_id):
                return
    except Exception:
        return

    wireframe_count = sum(
        1 for item in context.snapshot.slides if item.preview_kind == "wireframe"
    )
    if wireframe_count <= 0 and context.layout_ready_count <= 0:
        return

    shown = wireframe_count if wireframe_count > 0 else context.layout_ready_count
    st.info(
        f"当前为 Genesis 线框预览（{shown}/{context.slide_count} 页）。"
        "运行「生成」页汇报管线可升级为正式版式与截图。"
    )
    cols = st.columns(2)
    with cols[0]:
        if st.button(
            "前往生成",
            key=f"studio_wireframe_generate_{context.presentation.id}",
            width="stretch",
        ):
            st.switch_page(get_app_page("generate"))
    with cols[1]:
        if st.button(
            "全稿鸟瞰",
            key=f"studio_wireframe_overview_{context.presentation.id}",
            width="stretch",
        ):
            from archium.ui.studio.studio_pending_state import request_center_mode

            request_center_mode("overview")
            st.rerun()


def _render_partner_right_rail(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
    advanced: bool,
    project_id: UUID,
    presentation_id: UUID,
) -> None:
    """Design Assistant primary; inspector tools in collapsed expander."""
    from archium.ui.studio.design_assistant_panel import render_design_assistant_panel

    render_design_assistant_panel(slide_snapshot=slide_snapshot)
    expanded = bool(st.session_state.get("studio_inspector_expanded", False))
    inspector = st.expander(
        "检查器（属性 / 布局 / 内容 / 修改…）",
        expanded=expanded,
        on_change="rerun",
    )
    if inspector.open:
        with inspector:
            _render_inspector_tabs(
                slide_snapshot=slide_snapshot,
                advanced=advanced,
                project_id=project_id,
                presentation_id=presentation_id,
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
        from archium.ui.components.chrome import render_page_header

        render_page_header(
            "工作室",
            "故事线导航 · 页面画布 · AI 建议。不是拖文本框的 PowerPoint 克隆。",
        )

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

    from archium.ui.studio.studio_pending_state import apply_pending_studio_chrome

    apply_pending_studio_chrome()

    # Partner defaults: keep storyline + suggestions visible
    if "studio_show_nav" not in st.session_state:
        st.session_state.studio_show_nav = True
    if "studio_show_inspector" not in st.session_state:
        st.session_state.studio_show_inspector = True

    _render_studio_partner_strip(context)

    welcome = st.session_state.pop("studio_genesis_welcome", None)
    if isinstance(welcome, str) and welcome.strip():
        st.success(welcome)

    _render_wireframe_mode_banner(context)

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
            try:
                narrative = load_studio_narrative(context.presentation.id)
                selected_index = render_storyline_navigator(
                    context=context, bundle=narrative
                )
            except Exception:
                selected_index = render_slide_navigator(context=context)

    slide_snapshot = get_selected_slide_snapshot(context, selected_index)

    center_mode = str(st.session_state.get("studio_center_mode", "edit"))
    with center_col:
        if center_mode == "overview":
            from archium.ui.studio.deck_overview_panel import render_deck_overview

            render_deck_overview(context=context)
        else:
            from archium.ui.studio.page_intelligence_strip import render_page_intelligence_strip

            render_page_intelligence_strip(slide_snapshot, advanced=advanced)
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
            _render_partner_right_rail(
                slide_snapshot=slide_snapshot,
                advanced=advanced,
                project_id=context.project.id,
                presentation_id=context.presentation.id,
            )
