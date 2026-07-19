"""Project and presentation selectors for Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.infrastructure.database.session import get_session
from archium.ui.label_map import STATUS_LABELS, entity_label
from archium.ui.studio_service import (
    StudioPresentationContext,
    list_studio_presentations,
    list_studio_projects,
    load_studio_context,
    studio_readiness_label,
)


def _init_studio_session_state() -> None:
    defaults = {
        "selected_project_id": None,
        "selected_presentation_id": None,
        "studio_selected_slide_index": 0,
        "studio_advanced_mode": False,
        "last_visual_workflow_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_studio_selection(
    *,
    visual_critic_reports: list[dict] | None = None,
    deck_qa_report: dict | None = None,
    preview_paths: list[str] | None = None,
    workflow_output_dir: str | None = None,
) -> StudioPresentationContext | None:
    """Render project/presentation pickers and return loaded studio context."""
    _init_studio_session_state()
    advanced = st.toggle(
        "高级模式（显示技术术语）",
        value=bool(st.session_state.studio_advanced_mode),
        key="studio_advanced_mode_toggle",
    )
    st.session_state.studio_advanced_mode = advanced

    selector_cols = st.columns([1, 1, 1.2])
    with get_session() as session:
        projects = list_studio_projects(session)
    if not projects:
        st.info("还没有项目。请先到「项目工作台」创建项目并生成汇报。")
        return None

    project_labels = {str(project.id): project.name for project in projects}
    project_options = list(project_labels.keys())
    default_project_index = 0
    if st.session_state.selected_project_id in project_options:
        default_project_index = project_options.index(st.session_state.selected_project_id)

    with selector_cols[0]:
        selected_project = st.selectbox(
            "当前项目",
            options=project_options,
            index=default_project_index,
            format_func=lambda value: project_labels[value],
            key="studio_project_select",
        )
    if selected_project != st.session_state.selected_project_id:
        st.session_state.selected_presentation_id = None
        st.session_state.studio_selected_slide_index = 0
    st.session_state.selected_project_id = selected_project
    project_id = UUID(selected_project)

    with get_session() as session:
        presentations = list_studio_presentations(session, project_id)
    if not presentations:
        st.warning("该项目还没有汇报。请先在「项目工作台」生成 Brief → Storyline → 页面内容。")
        return None

    presentation_labels = {
        str(item.id): f"{item.title} · {item.status.value}" for item in presentations
    }
    presentation_options = list(presentation_labels.keys())
    default_presentation_index = 0
    if st.session_state.selected_presentation_id in presentation_options:
        default_presentation_index = presentation_options.index(
            st.session_state.selected_presentation_id
        )

    with selector_cols[1]:
        selected_presentation = st.selectbox(
            entity_label("PresentationBrief", advanced=advanced) + " / 汇报",
            options=presentation_options,
            index=default_presentation_index,
            format_func=lambda value: presentation_labels[value],
            key="studio_presentation_select",
        )
    if selected_presentation != st.session_state.selected_presentation_id:
        st.session_state.studio_selected_slide_index = 0
    st.session_state.selected_presentation_id = selected_presentation
    presentation_id = UUID(selected_presentation)

    with get_session() as session:
        context = load_studio_context(
            session,
            project_id,
            presentation_id,
            visual_critic_reports=visual_critic_reports,
            deck_qa_report=deck_qa_report,
            preview_paths=preview_paths,
            workflow_output_dir=workflow_output_dir,
        )
    if context is None:
        st.error("无法加载汇报上下文。")
        return None

    readiness = studio_readiness_label(context)
    with selector_cols[2]:
        st.metric("版式就绪", f"{context.layout_ready_count}/{context.slide_count or 0}")
        st.metric("预览就绪", f"{context.preview_ready_count}/{context.slide_count or 0}")
        st.caption(STATUS_LABELS.get(readiness, readiness))
    return context
