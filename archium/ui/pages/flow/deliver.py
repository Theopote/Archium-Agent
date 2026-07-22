"""Product-flow stage: 交付 — readiness / QA / export / version records."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.visual.visual_workflow_service import VisualWorkflowResult
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.pages.flow import render_stage_header, render_stage_nav
from archium.ui.studio.export_panel import render_export_panel
from archium.ui.studio_service import (
    get_selected_slide_snapshot,
    list_studio_presentations,
    list_studio_projects,
    load_studio_context,
)


def _workflow_artifacts() -> tuple[list[dict] | None, dict | None, list[str] | None, str | None]:
    result = st.session_state.get("last_visual_workflow_result")
    if not isinstance(result, VisualWorkflowResult):
        return None, None, None, None
    deck_qa = result.deck_qa_report if isinstance(result.deck_qa_report, dict) else None
    critics = list(result.visual_critic_reports or [])
    previews = list(result.render_paths or [])
    output_dir = result.workflow_run.state.get("output_dir")
    return critics, deck_qa, previews, output_dir if isinstance(output_dir, str) else None


def _render_simple_selection():
    """Lightweight project + presentation pick — no Studio advanced chrome."""
    from archium.ui.pages.workspace import ensure_workspace_session

    ensure_workspace_session()
    with get_session() as session:
        projects = list_studio_projects(session)
    if not projects:
        return None

    labels = {str(project.id): project.name for project in projects}
    options = list(labels.keys())
    default_index = 0
    if st.session_state.get("selected_project_id") in options:
        default_index = options.index(st.session_state.selected_project_id)

    selected_project = st.selectbox(
        "项目",
        options=options,
        index=default_index,
        format_func=lambda value: labels[value],
        key="deliver_project_select",
    )
    if selected_project != st.session_state.get("selected_project_id"):
        st.session_state.selected_presentation_id = None
    st.session_state.selected_project_id = selected_project
    project_id = UUID(selected_project)

    with get_session() as session:
        presentations = list_studio_presentations(session, project_id)
    if not presentations:
        st.caption("当前项目尚无汇报可导出。")
        return None

    presentation_labels = {
        str(item.id): f"{item.title} · {item.status.value}" for item in presentations
    }
    presentation_options = list(presentation_labels.keys())
    default_presentation = 0
    if st.session_state.get("selected_presentation_id") in presentation_options:
        default_presentation = presentation_options.index(
            st.session_state.selected_presentation_id
        )
    selected_presentation = st.selectbox(
        "汇报版本",
        options=presentation_options,
        index=default_presentation,
        format_func=lambda value: presentation_labels[value],
        key="deliver_presentation_select",
    )
    st.session_state.selected_presentation_id = selected_presentation

    critics, deck_qa, previews, workflow_output_dir = _workflow_artifacts()
    with get_session() as session:
        return load_studio_context(
            session,
            project_id=project_id,
            presentation_id=UUID(selected_presentation),
            visual_critic_reports=critics,
            deck_qa_report=deck_qa,
            preview_paths=previews,
            workflow_output_dir=workflow_output_dir,
        )


def _render_readiness(context: object) -> None:
    st.markdown("#### 准备度")
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
    cols[2].metric("待处理页", pending if pending else warn_count)
    cols[3].metric("阻塞项", blocker_count)


def _render_qa(project_id: UUID) -> None:
    st.markdown("#### QA")
    st.caption("导出前快速检查质量问题。研发 Benchmark 在「设置 → 开发者与验收」。")
    from archium.ui.pages.workspace import render_review_stage

    with st.expander("打开质量检查", expanded=False):
        render_review_stage(project_id)


def _render_delivery_records() -> None:
    st.markdown("#### 版本记录")
    records = list(st.session_state.get("delivery_export_records") or [])
    if not records:
        st.caption("尚无导出记录。完成导出后会显示格式、时间与路径。")
        return
    for item in reversed(records[-12:]):
        st.markdown(
            f"- **{item.get('format', '文件')}** · {item.get('when', '')}"
            f" · `{item.get('path', '')}`"
        )


def render() -> None:
    render_stage_header("deliver")
    st.caption("准备度、QA、导出与版本记录。不在此页做 Benchmark 或复杂工作室配置。")

    context = _render_simple_selection()
    if context is None:
        st.warning("尚未选择可导出的汇报。请先在「生成」或「工作室」准备页面内容。")
        from archium.ui import icons

        st.page_link(get_app_page("materials"), label="前往资料", icon=icons.MATERIALS)
        st.page_link(get_app_page("generate"), label="前往生成", icon=icons.GENERATE)
        render_stage_nav("deliver")
        return

    _render_readiness(context)
    st.divider()
    _render_qa(context.project.id)
    st.divider()

    selected_index = int(st.session_state.get("studio_selected_slide_index", 0))
    slide_snapshot = get_selected_slide_snapshot(context, selected_index)
    st.markdown("#### 导出")
    st.caption("选择格式并导出。路径写入下方版本记录。")
    render_export_panel(context=context, slide_snapshot=slide_snapshot)

    st.divider()
    _render_delivery_records()
    st.divider()
    render_stage_nav("deliver")
