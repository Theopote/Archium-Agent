"""Streamlit visual composition / design page."""

from __future__ import annotations

from typing import cast
from uuid import UUID

import streamlit as st

from archium.application.visual.visual_workflow_service import VisualWorkflowResult
from archium.domain.visual.enums import (
    DecorationLevel,
    DensityLevel,
    DrawingDisplayMode,
    FormalityLevel,
    PresentationContext,
    VisualEmphasis,
    WhitespacePreference,
)
from archium.domain.visual.preferences import VisualPreferences
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.art_direction_panel import render_art_direction_panel
from archium.ui.error_handlers import format_user_error
from archium.ui.layout_family_ui import format_layout_family_label
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.slide_visual_panel import render_slide_visual_panel
from archium.ui.visual_capability_panel import render_visual_engine_scope
from archium.ui.visual_service import (
    continue_visual_after_layout_review,
    get_presentation_visual_snapshot,
    run_visual_workflow,
)
from archium.ui.workspace_service import list_project_presentations, list_projects

DENSITY_LABELS = {
    DensityLevel.SPACIOUS: "疏朗",
    DensityLevel.BALANCED: "均衡",
    DensityLevel.COMPACT: "紧凑",
}
EMPHASIS_LABELS = {
    VisualEmphasis.IMAGE_LED: "图像主导",
    VisualEmphasis.DRAWING_LED: "图纸主导",
    VisualEmphasis.TEXT_LED: "文字主导",
    VisualEmphasis.BALANCED: "均衡",
}
FORMALITY_LABELS = {
    FormalityLevel.CASUAL: "轻松",
    FormalityLevel.PROFESSIONAL: "专业",
    FormalityLevel.FORMAL: "正式",
    FormalityLevel.CEREMONIAL: "仪式感",
}
DECORATION_LABELS = {
    DecorationLevel.NONE: "无装饰",
    DecorationLevel.LOW: "低",
    DecorationLevel.MEDIUM: "中",
    DecorationLevel.HIGH: "高",
}
WHITESPACE_LABELS = {
    WhitespacePreference.TIGHT: "紧凑",
    WhitespacePreference.BALANCED: "均衡",
    WhitespacePreference.GENEROUS: "充裕",
}
DRAWING_LABELS = {
    DrawingDisplayMode.CLEAR: "清晰可读",
    DrawingDisplayMode.ANNOTATED: "带标注",
    DrawingDisplayMode.CONTEXTUAL: "情境化",
}
CONTEXT_LABELS = {
    PresentationContext.CLIENT_REVIEW: "甲方汇报",
    PresentationContext.GOVERNMENT_REVIEW: "政府审查",
    PresentationContext.DESIGN_COMPETITION: "设计竞赛",
    PresentationContext.INTERNAL_CRITIQUE: "内部评图",
    PresentationContext.TECHNICAL_REPORT: "技术报告",
    PresentationContext.ACADEMIC_RESEARCH: "学术研究",
}


def _init_session_state() -> None:
    defaults = {
        "selected_project_id": None,
        "selected_presentation_id": None,
        "last_visual_workflow_result": None,
        "visual_workflow_run_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_project_selector() -> UUID | None:
    with get_session() as session:
        projects = list_projects(session)
    if not projects:
        st.info("还没有项目。请先到「项目工作台」创建项目并生成汇报。")
        return None

    labels = {str(project.id): project.name for project in projects}
    options = list(labels.keys())
    default_index = 0
    if st.session_state.selected_project_id in options:
        default_index = options.index(st.session_state.selected_project_id)

    selected = st.selectbox(
        "当前项目",
        options=options,
        index=default_index,
        format_func=lambda value: labels[value],
        key="visual_project_select",
    )
    if selected != st.session_state.selected_project_id:
        st.session_state.selected_presentation_id = None
    st.session_state.selected_project_id = selected
    return UUID(selected)


def _render_presentation_selector(project_id: UUID) -> UUID | None:
    with get_session() as session:
        presentations = list_project_presentations(session, project_id)
    if not presentations:
        st.warning("该项目还没有 Presentation。请先在「项目工作台」生成 Brief → Storyline → SlideSpec。")
        return None

    labels = {
        str(item.id): f"{item.title} · {item.status.value}"
        for item in presentations
    }
    options = list(labels.keys())
    default_index = 0
    if st.session_state.selected_presentation_id in options:
        default_index = options.index(st.session_state.selected_presentation_id)

    selected = st.selectbox(
        "当前汇报",
        options=options,
        index=default_index,
        format_func=lambda value: labels[value],
        key="visual_presentation_select",
    )
    st.session_state.selected_presentation_id = selected
    return UUID(selected)


def _render_preferences_form() -> tuple[VisualPreferences, dict[str, object]]:
    st.markdown("#### 视觉偏好")
    col1, col2, col3 = st.columns(3)
    with col1:
        density = st.selectbox(
            "信息密度",
            options=list(DENSITY_LABELS.keys()),
            format_func=lambda value: DENSITY_LABELS[value],
            index=list(DENSITY_LABELS.keys()).index(DensityLevel.BALANCED),
            key="visual_pref_density",
        )
        emphasis = st.selectbox(
            "视觉重心",
            options=list(EMPHASIS_LABELS.keys()),
            format_func=lambda value: EMPHASIS_LABELS[value],
            index=list(EMPHASIS_LABELS.keys()).index(VisualEmphasis.BALANCED),
            key="visual_pref_emphasis",
        )
    with col2:
        formality = st.selectbox(
            "正式程度",
            options=list(FORMALITY_LABELS.keys()),
            format_func=lambda value: FORMALITY_LABELS[value],
            index=list(FORMALITY_LABELS.keys()).index(FormalityLevel.PROFESSIONAL),
            key="visual_pref_formality",
        )
        decoration = st.selectbox(
            "装饰强度",
            options=list(DECORATION_LABELS.keys()),
            format_func=lambda value: DECORATION_LABELS[value],
            index=list(DECORATION_LABELS.keys()).index(DecorationLevel.LOW),
            key="visual_pref_decoration",
        )
    with col3:
        whitespace = st.selectbox(
            "留白偏好",
            options=list(WHITESPACE_LABELS.keys()),
            format_func=lambda value: WHITESPACE_LABELS[value],
            index=list(WHITESPACE_LABELS.keys()).index(WhitespacePreference.BALANCED),
            key="visual_pref_whitespace",
        )
        drawing_mode = st.selectbox(
            "图纸显示",
            options=list(DRAWING_LABELS.keys()),
            format_func=lambda value: DRAWING_LABELS[value],
            index=list(DRAWING_LABELS.keys()).index(DrawingDisplayMode.CLEAR),
            key="visual_pref_drawing",
        )

    context = st.selectbox(
        "汇报场景",
        options=list(CONTEXT_LABELS.keys()),
        format_func=lambda value: CONTEXT_LABELS[value],
        index=list(CONTEXT_LABELS.keys()).index(PresentationContext.CLIENT_REVIEW),
        key="visual_pref_context",
    )

    run_opts_col1, run_opts_col2, run_opts_col3 = st.columns(3)
    with run_opts_col1:
        require_review = st.checkbox("需要批准视觉方向", value=True, key="visual_require_review")
    with run_opts_col2:
        use_llm = st.checkbox("使用 LLM（可选）", value=False, key="visual_use_llm")
    with run_opts_col3:
        export_pptx = st.checkbox("同时导出 PPTX", value=False, key="visual_export_pptx")

    preferences = VisualPreferences(
        density=density,
        visual_emphasis=emphasis,
        formality=formality,
        decoration_level=decoration,
        whitespace_preference=whitespace,
        drawing_display_mode=drawing_mode,
        presentation_context=context,
    )
    options: dict[str, object] = {
        "require_art_direction_review": require_review,
        "use_llm": use_llm,
        "export_pptx": export_pptx,
        "candidate_count": 3,
    }
    return preferences, options


def _render_run_section(project_id: UUID, presentation_id: UUID) -> None:
    preferences, options = _render_preferences_form()
    settings = get_ui_effective_settings()
    if options["use_llm"] and not settings.llm_configured:
        st.caption("当前未配置 API Key，将自动回退到规则生成。")

    if st.button("生成视觉编排", type="primary", use_container_width=True):
        try:
            with (
                st.spinner("正在生成视觉方向与版式…"),
                get_session() as session,
            ):
                result = run_visual_workflow(
                    session,
                    project_id,
                    presentation_id,
                    preferences=preferences,
                    require_art_direction_review=bool(
                        options["require_art_direction_review"]
                    ),
                    use_llm=bool(options["use_llm"]),
                    export_pptx=bool(options["export_pptx"]),
                    candidate_count=int(cast(int, options["candidate_count"])),
                )
            st.session_state.last_visual_workflow_result = result
            st.session_state.visual_workflow_run_id = str(result.workflow_run.id)
            if result.awaiting_review:
                if result.review_gate == "layout_review":
                    st.warning(
                        "版式仍有 ERROR/CRITICAL 问题，已暂停导出。"
                        "请在「单页视觉」中调整后，于预览页继续。"
                    )
                else:
                    st.info("已生成视觉方向，等待批准后继续。")
            elif result.succeeded:
                st.success("视觉编排完成。")
            else:
                detail = "；".join(result.errors) if result.errors else "未知错误"
                st.error(f"视觉编排未完成：{detail}")
            st.rerun()
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        except Exception as exc:
            st.error(format_user_error(exc))


def _render_result_summary() -> None:
    result = st.session_state.last_visual_workflow_result
    if result is None:
        return
    st.markdown("#### 最近一次编排结果")
    cols = st.columns(4)
    cols[0].metric("状态", result.workflow_run.status.value)
    cols[1].metric("意图数", len(result.visual_intent_ids))
    cols[2].metric("版式数", len(result.layout_plan_ids))
    deck_score = (
        result.deck_qa_report.get("total_score")
        if isinstance(result.deck_qa_report, dict)
        else None
    )
    cols[3].metric(
        "Deck QA",
        f"{deck_score:.2f}" if isinstance(deck_score, (int, float)) else str(len(result.render_paths)),
    )
    if result.warnings:
        st.caption("警告：" + "；".join(result.warnings))

    _render_quality_reports(result)

    if result.render_paths:
        with st.expander("输出文件", expanded=False):
            for path in result.render_paths:
                st.code(path, language=None)

    awaiting_layout = bool(
        result.awaiting_review and result.review_gate == "layout_review"
    )
    if awaiting_layout:
        st.warning(
            "版式审核门：存在 ERROR/CRITICAL，禁止静默导出 PPTX。"
            "可先在「单页视觉」重排，再继续（仍不会导出无效 PPTX）。"
        )
        if st.button("继续工作流（跳过无效 PPTX）", type="primary", use_container_width=True):
            try:
                with get_session() as session:
                    continued = continue_visual_after_layout_review(
                        session,
                        result.workflow_run.id,
                        allow_invalid_layout_export=True,
                    )
                st.session_state.last_visual_workflow_result = continued
                st.rerun()
            except Exception as exc:
                st.error(format_user_error(exc))


def _render_quality_reports(result: VisualWorkflowResult) -> None:
    """Show Deck QA + Visual Critic from the last workflow run (read-only)."""
    deck = result.deck_qa_report if isinstance(result.deck_qa_report, dict) else None
    critics = list(result.visual_critic_reports or [])
    if deck is None and not critics:
        return

    st.markdown("**视觉可靠性（只读）**")
    st.caption("Visual Critic / Deck QA 不参与 PPTX 门禁，也不自动修复版式。")

    if deck is not None:
        score = deck.get("total_score")
        dims = deck.get("dimensions") or {}
        with st.expander(
            f"Deck QA · 一致性 "
            f"{f'{score:.2f}' if isinstance(score, (int, float)) else '—'}",
            expanded=bool(deck.get("findings")),
        ):
            dim_line = " · ".join(
                f"{key}={value:.2f}"
                for key, value in dims.items()
                if isinstance(value, (int, float))
            )
            st.write(dim_line or "暂无维度分")
            for item in list(deck.get("findings") or [])[:12]:
                st.write(
                    f"- `{item.get('rule_code')}` · {item.get('severity')} · "
                    f"{item.get('message')}"
                )

    if critics:
        with st.expander(f"Visual Critic · 共 {len(critics)} 页", expanded=False):
            rows = []
            for report in critics:
                total = report.get("total_score")
                findings = report.get("findings") or []
                rows.append(
                    {
                        "slide": str(report.get("slide_id") or "")[:8],
                        "视觉质量": (
                            f"{total:.2f}" if isinstance(total, (int, float)) else "—"
                        ),
                        "发现数": len(findings),
                        "截图": "有" if report.get("source_image") else "无",
                        "codes": ", ".join(
                            sorted({str(item.get("rule_code")) for item in findings})
                        )
                        or "—",
                    }
                )
            st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_composition_tabs(presentation_id: UUID) -> None:
    result = st.session_state.last_visual_workflow_result
    with get_session() as session:
        snapshot = get_presentation_visual_snapshot(
            session,
            presentation_id,
            visual_critic_reports=(
                list(result.visual_critic_reports) if result is not None else None
            ),
            deck_qa_report=(
                result.deck_qa_report
                if result is not None and isinstance(result.deck_qa_report, dict)
                else None
            ),
            preview_paths=list(result.render_paths) if result is not None else None,
        )

    awaiting = bool(result and result.awaiting_review and result.review_gate == "art_direction")
    workflow_run_id = None
    if result is not None:
        workflow_run_id = result.workflow_run.id
    elif st.session_state.visual_workflow_run_id:
        workflow_run_id = UUID(st.session_state.visual_workflow_run_id)

    tab_direction, tab_slides, tab_preview = st.tabs(
        ["视觉方向", "单页视觉", "预览与产物"]
    )

    with tab_direction:
        if snapshot.art_direction is None:
            st.caption("尚未生成 ArtDirection。请先点击「生成视觉编排」。")
        else:
            render_art_direction_panel(
                art_direction=snapshot.art_direction,
                workflow_run_id=workflow_run_id if awaiting else None,
                awaiting_approval=awaiting,
            )
            if snapshot.design_system is not None:
                with st.expander("DesignSystem", expanded=False):
                    ds = snapshot.design_system
                    st.write(f"名称：{ds.name}")
                    st.write(f"页面：{ds.page.width} × {ds.page.height} {ds.page.unit}")
                    st.write(f"网格：{ds.grid.columns} 栏 · {ds.grid.grid_type.value}")
                    st.write(f"正文字号：{ds.typography.body.font_size} pt")

    with tab_slides:
        if not snapshot.slides:
            st.caption("当前汇报没有页面。")
        else:
            for item in snapshot.slides:
                with st.container(border=True):
                    render_slide_visual_panel(snapshot=item)

    with tab_preview:
        _render_result_summary()
        if snapshot.design_system is not None:
            st.caption(
                f"DesignSystem：{snapshot.design_system.name} · "
                f"{snapshot.design_system.page.width}×{snapshot.design_system.page.height}"
            )
        st.markdown("**版式概览**")
        rows = []
        for item in snapshot.slides:
            plan = item.layout_plan
            intent = item.visual_intent
            critic_score = None
            if item.visual_critic is not None:
                critic_score = item.visual_critic.get("total_score")
            rows.append(
                {
                    "页码": item.slide.order + 1,
                    "标题": item.slide.title,
                    "内容类型": intent.dominant_content_type.value if intent else "—",
                    "版式族": (
                        format_layout_family_label(plan.layout_family)
                        if plan
                        else "—"
                    ),
                    "变体": plan.layout_variant if plan else "—",
                    "版式质量": (
                        f"{item.validation.score:.2f}"
                        if item.validation is not None
                        else "—"
                    ),
                    "视觉质量": (
                        f"{critic_score:.2f}"
                        if isinstance(critic_score, (int, float))
                        else "—"
                    ),
                    "校验": (
                        "通过"
                        if item.validation is not None and item.validation.valid
                        else ("问题" if item.validation is not None else "—")
                    ),
                }
            )
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.caption("暂无版式数据。")


def render() -> None:
    _init_session_state()
    st.markdown("### 视觉设计")
    st.caption(
        "为已有 SlideSpec 生成 ArtDirection、VisualIntent 与 LayoutPlan；"
        "导出时按 LayoutPlan 坐标执行 PPTX（不重排版式）。"
    )
    render_visual_engine_scope()

    project_id = _render_project_selector()
    if project_id is None:
        return

    presentation_id = _render_presentation_selector(project_id)
    if presentation_id is None:
        return

    st.divider()
    _render_run_section(project_id, presentation_id)
    st.divider()
    _render_composition_tabs(presentation_id)
