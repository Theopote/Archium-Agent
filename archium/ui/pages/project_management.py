"""Project management page - view, edit, and delete projects."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import streamlit as st

from archium.application.project_deletion_service import ProjectDeletionService
from archium.application.project_management_service import ProjectManagementService
from archium.domain.enums import ProjectOriginMode
from archium.domain.project import Project
from archium.exceptions import ProjectNotFoundError, ValidationError
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.error_handlers import report_user_error


def _format_datetime(dt: datetime | None) -> str:
    if dt is None:
        return "未知"
    return dt.strftime("%Y-%m-%d %H:%M")


def _render_project_card(project: Project, index: int) -> None:
    with st.container():
        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            st.markdown(f"### {project.name}")
            if project.description:
                st.caption(project.description)
            else:
                st.caption("_无描述_")

        with col2:
            st.caption(f"创建时间: {_format_datetime(project.created_at)}")
            st.caption(f"更新时间: {_format_datetime(project.updated_at)}")

        with col3:
            if st.button("✏️ 编辑", key=f"edit_{project.id}", use_container_width=True):
                st.session_state.editing_project_id = str(project.id)
                st.session_state.editing_project_updated_at = project.updated_at.isoformat()
                st.rerun()

            if st.button("🗑️ 删除", key=f"delete_{project.id}", use_container_width=True, type="secondary"):
                st.session_state.deleting_project_id = str(project.id)
                st.rerun()

            if st.button("📂 打开", key=f"open_{project.id}", use_container_width=True, type="primary"):
                st.session_state.selected_project_id = str(project.id)
                if project.origin_mode == ProjectOriginMode.CONCEPT_EXPLORATION:
                    st.switch_page(get_app_page("project-mission"))
                else:
                    st.switch_page(get_app_page("materials"))

        st.divider()


def _render_edit_dialog(project_id: UUID, expected_updated_at: datetime | None) -> None:
    try:
        with get_session() as session:
            project = ProjectManagementService(session).get_project(project_id)
    except ProjectNotFoundError:
        st.warning("项目不存在或已被删除。")
        st.session_state.editing_project_id = None
        st.session_state.editing_project_updated_at = None
        return

    st.subheader(f"编辑项目: {project.name}")

    with st.form(key="edit_project_form"):
        new_name = st.text_input("项目名称", value=project.name)
        new_description = st.text_area("项目描述", value=project.description or "")

        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("💾 保存", use_container_width=True, type="primary")
        with col2:
            cancel = st.form_submit_button("❌ 取消", use_container_width=True)

        if submit:
            try:
                with get_session() as session:
                    ProjectManagementService(session).update_project(
                        project_id,
                        name=new_name,
                        description=new_description,
                        expected_updated_at=expected_updated_at,
                    )
                st.success("✅ 项目已更新")
                st.session_state.editing_project_id = None
                st.session_state.editing_project_updated_at = None
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))

        if cancel:
            st.session_state.editing_project_id = None
            st.session_state.editing_project_updated_at = None
            st.rerun()


def _render_delete_confirmation(project_id: UUID) -> None:
    try:
        with get_session() as session:
            project = ProjectManagementService(session).get_project(project_id)
    except ProjectNotFoundError:
        st.warning("项目不存在或已被删除。")
        st.session_state.deleting_project_id = None
        return

    st.warning(f"⚠️ 确定要删除项目「{project.name}」吗？")
    st.markdown("**此操作不可撤销**，将删除：")
    st.markdown("""
    - 项目记录及数据库中的关联数据（汇报、幻灯片、布局方案、任务与修订等）
    - 项目上传的文档与素材文件
    - 项目向量检索索引
    - 相关导出与 Studio 输出（预览、Marp/PPTX、视觉合成、审阅记录等）
    """)
    st.caption(
        "删除由应用层分阶段执行：先标记并隔离项目文件，数据库记录删除成功后再清理向量与输出缓存。"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 确认删除", use_container_width=True, type="primary"):
            try:
                with get_session() as session:
                    result = ProjectDeletionService(session).delete_project(project_id)
                st.success("✅ 项目已删除")
                if result.warnings:
                    for _warning in result.warnings:
                        st.warning("部分关联资源未能清理，项目记录已删除。")
                st.session_state.deleting_project_id = None
                st.session_state.selected_project_id = None
                st.rerun()
            except Exception as exc:
                st.error(report_user_error(exc))

    with col2:
        if st.button("❌ 取消", use_container_width=True):
            st.session_state.deleting_project_id = None
            st.rerun()


def _render_create_project_form() -> None:
    st.subheader("创建新项目")

    with st.form(key="create_project_form"):
        project_name = st.text_input("项目名称", placeholder="例如：某某文化中心方案汇报")
        project_description = st.text_area(
            "项目描述（可选）",
            placeholder="简要描述项目背景、目标等信息",
        )

        submit = st.form_submit_button("➕ 创建项目", use_container_width=True, type="primary")

        if submit:
            try:
                with get_session() as session:
                    created_project = ProjectManagementService(session).create_project(
                        project_name,
                        project_description,
                    )
                st.success(f"✅ 项目「{created_project.name}」创建成功")
                st.session_state.selected_project_id = str(created_project.id)
                st.session_state.show_create_form = False
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))


def render() -> None:
    """Render the project management page."""
    st.title("项目管理")
    st.markdown("管理你的所有项目，查看、编辑或删除项目。")

    if "editing_project_id" not in st.session_state:
        st.session_state.editing_project_id = None
    if "editing_project_updated_at" not in st.session_state:
        st.session_state.editing_project_updated_at = None
    if "deleting_project_id" not in st.session_state:
        st.session_state.deleting_project_id = None
    if "show_create_form" not in st.session_state:
        st.session_state.show_create_form = False

    with get_session() as session:
        projects = ProjectManagementService(session).list_projects()

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button(
            "➕ 新建项目",
            use_container_width=True,
            type="primary",
            disabled=st.session_state.show_create_form,
        ):
            st.session_state.show_create_form = True
            st.rerun()

    if st.session_state.show_create_form:
        _render_create_project_form()
        st.divider()

    if not projects:
        st.info("🎯 还没有项目，点击上方「新建项目」开始。")
        return

    st.markdown(f"### 所有项目 ({len(projects)})")

    if st.session_state.editing_project_id:
        expected_updated_at = None
        if st.session_state.editing_project_updated_at:
            expected_updated_at = datetime.fromisoformat(
                st.session_state.editing_project_updated_at
            )
        _render_edit_dialog(UUID(st.session_state.editing_project_id), expected_updated_at)
        st.divider()

    if st.session_state.deleting_project_id:
        _render_delete_confirmation(UUID(st.session_state.deleting_project_id))
        st.divider()

    for index, project in enumerate(projects):
        if (
            st.session_state.editing_project_id == str(project.id)
            or st.session_state.deleting_project_id == str(project.id)
        ):
            continue
        _render_project_card(project, index)

    st.markdown("---")
    st.markdown("### 快速导航")
    link_cols = st.columns(3)
    with link_cols[0]:
        st.page_link(get_app_page("home"), label="返回概览", icon="🏠")
    with link_cols[1]:
        st.page_link(get_app_page("outline"), label="开始大纲", icon=":material/account_tree:")
    with link_cols[2]:
        st.page_link(get_app_page("materials"), label="进入资料", icon=":material/folder_open:")
