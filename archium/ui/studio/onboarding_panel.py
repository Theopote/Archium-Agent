"""Project creation and document import inside Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.config.settings import Settings
from archium.domain.enums import ProjectType
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.studio_service import (
    create_studio_project,
    get_studio_project_overview,
    import_studio_file,
)
from archium.ui.pages.workspace import PROJECT_TYPE_LABELS


def render_studio_onboarding() -> None:
    """Render first-run project creation when no projects exist."""
    st.markdown("**开始第一个项目**")
    st.caption("可在工作室内创建项目并导入资料，无需先离开本页。")
    with st.form("studio_create_project_form"):
        name = st.text_input("项目名称", placeholder="例如：某医院老院区更新")
        project_type = st.selectbox(
            "项目类型",
            options=list(PROJECT_TYPE_LABELS.keys()),
            format_func=lambda value: PROJECT_TYPE_LABELS[value],
        )
        description = st.text_area("项目说明（可选）", height=80)
        submitted = st.form_submit_button("创建项目", type="primary", use_container_width=True)
        if submitted:
            if not name.strip():
                st.error("请填写项目名称。")
                return
            try:
                with get_session() as session:
                    project = create_studio_project(
                        session,
                        name=name,
                        project_type=project_type,
                        description=description,
                    )
                st.session_state.selected_project_id = str(project.id)
                st.session_state.selected_presentation_id = None
                st.success(f"已创建项目：{project.name}")
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))


def render_studio_import_panel(*, project_id: UUID, expanded: bool = False) -> None:
    """Render document upload for the selected studio project."""
    with get_session() as session:
        overview = get_studio_project_overview(session, project_id)
    if overview is None:
        return

    with st.expander("项目资料与导入", expanded=expanded):
        st.caption(
            f"已导入 {overview.document_count} 个文件 · "
            f"{overview.chunk_count} 个文本片段 · "
            f"{overview.presentation_count} 个汇报"
        )
        uploads = st.file_uploader(
            "上传项目资料",
            type=["pdf", "docx", "pptx", "xlsx", "png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key=f"studio_upload_{project_id}",
        )
        if uploads and st.button("开始导入", key=f"studio_import_{project_id}"):
            settings = get_ui_effective_settings()
            _run_import(project_id, uploads, settings=settings)


def render_studio_no_presentation_hint(*, project_id: UUID) -> None:
    """Guide user when project exists but has no presentation yet."""
    render_studio_import_panel(project_id=project_id, expanded=True)
    st.warning("该项目还没有汇报内容。请导入资料后，到项目工作台或项目任务生成页面内容。")
    link_cols = st.columns(2)
    with link_cols[0]:
        st.page_link("project-mission", label="前往项目任务", icon="🧭")
    with link_cols[1]:
        st.page_link("workspace", label="前往项目工作台", icon="📁")


def _run_import(project_id: UUID, uploads: list, *, settings: Settings) -> None:
    results = []
    try:
        with get_session() as session:
            for upload in uploads:
                results.append(
                    import_studio_file(
                        session,
                        project_id,
                        filename=upload.name,
                        data=upload.getvalue(),
                        settings=settings,
                    )
                )
    except WorkflowError as exc:
        st.error(format_user_error(exc))
        return
    except Exception as exc:
        st.error(format_user_error(exc))
        return

    for result in results:
        if result.error:
            st.error(f"{result.source_path.name}: {result.error}")
        elif result.duplicate:
            st.warning(f"{result.source_path.name}: 已存在相同文件，已跳过")
        else:
            chunk_count = len(result.chunks)
            st.success(f"{result.source_path.name}: 导入成功（{chunk_count} 个片段）")
    st.rerun()
