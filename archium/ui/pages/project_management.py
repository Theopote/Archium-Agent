"""Project management page - view, edit, and delete projects."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import streamlit as st

from archium.domain.project import Project
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page


def _format_datetime(dt: datetime | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return "未知"
    return dt.strftime("%Y-%m-%d %H:%M")


def _render_project_card(project: Project, index: int) -> None:
    """Render a single project card with actions."""
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
            if hasattr(project, 'updated_at') and project.updated_at:
                st.caption(f"更新时间: {_format_datetime(project.updated_at)}")

        with col3:
            # Edit button
            if st.button("✏️ 编辑", key=f"edit_{project.id}", use_container_width=True):
                st.session_state.editing_project_id = str(project.id)
                st.rerun()

            # Delete button
            if st.button("🗑️ 删除", key=f"delete_{project.id}", use_container_width=True, type="secondary"):
                st.session_state.deleting_project_id = str(project.id)
                st.rerun()

            # Open button
            if st.button("📂 打开", key=f"open_{project.id}", use_container_width=True, type="primary"):
                st.session_state.selected_project_id = str(project.id)
                st.switch_page(get_app_page("workspace"))

        st.divider()


def _render_edit_dialog(project: Project) -> None:
    """Render edit dialog for a project."""
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
            if not new_name.strip():
                st.error("项目名称不能为空")
            else:
                try:
                    with get_session() as session:
                        repo = ProjectRepository(session)
                        project.name = new_name.strip()
                        project.description = new_description.strip() or None
                        repo.update(project)
                        session.commit()
                    st.success("✅ 项目已更新")
                    st.session_state.editing_project_id = None
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 更新失败: {e}")

        if cancel:
            st.session_state.editing_project_id = None
            st.rerun()


def _render_delete_confirmation(project: Project) -> None:
    """Render delete confirmation dialog."""
    st.warning(f"⚠️ 确定要删除项目「{project.name}」吗？")
    st.markdown("**此操作不可撤销**，将删除：")
    st.markdown("""
    - 项目下的所有汇报 (Presentations)
    - 所有幻灯片 (Slides)
    - 所有布局方案 (LayoutPlans)
    - 所有导入的文档和资料
    """)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 确认删除", use_container_width=True, type="primary"):
            try:
                with get_session() as session:
                    repo = ProjectRepository(session)
                    # TODO: 实现级联删除逻辑
                    # 目前只删除项目本身，需要补充删除关联数据
                    repo.delete(project.id)
                    session.commit()
                st.success("✅ 项目已删除")
                st.session_state.deleting_project_id = None
                st.session_state.selected_project_id = None
                st.rerun()
            except Exception as e:
                st.error(f"❌ 删除失败: {e}")

    with col2:
        if st.button("❌ 取消", use_container_width=True):
            st.session_state.deleting_project_id = None
            st.rerun()


def _render_create_project_form() -> None:
    """Render form to create a new project."""
    st.subheader("创建新项目")

    with st.form(key="create_project_form"):
        project_name = st.text_input("项目名称", placeholder="例如：某某文化中心方案汇报")
        project_description = st.text_area(
            "项目描述（可选）",
            placeholder="简要描述项目背景、目标等信息",
        )

        submit = st.form_submit_button("➕ 创建项目", use_container_width=True, type="primary")

        if submit:
            if not project_name.strip():
                st.error("项目名称不能为空")
            else:
                try:
                    with get_session() as session:
                        repo = ProjectRepository(session)
                        new_project = Project(
                            name=project_name.strip(),
                            description=project_description.strip() or None,
                        )
                        created_project = repo.create(new_project)
                        session.commit()
                    st.success(f"✅ 项目「{created_project.name}」创建成功")
                    st.session_state.selected_project_id = str(created_project.id)
                    # Collapse the create form
                    st.session_state.show_create_form = False
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 创建失败: {e}")


def render() -> None:
    """Render the project management page."""
    st.title("📁 项目管理")
    st.markdown("管理你的所有项目，查看、编辑或删除项目。")

    # Initialize session state
    if "editing_project_id" not in st.session_state:
        st.session_state.editing_project_id = None
    if "deleting_project_id" not in st.session_state:
        st.session_state.deleting_project_id = None
    if "show_create_form" not in st.session_state:
        st.session_state.show_create_form = False

    # Load projects
    with get_session() as session:
        repo = ProjectRepository(session)
        projects = repo.list_all()

    # Create project button
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

    # Show create form if toggled
    if st.session_state.show_create_form:
        _render_create_project_form()
        st.divider()

    # Show project list
    if not projects:
        st.info("🎯 还没有项目，点击上方「新建项目」开始。")
        return

    st.markdown(f"### 所有项目 ({len(projects)})")

    # Handle edit dialog
    if st.session_state.editing_project_id:
        editing_project = next(
            (p for p in projects if str(p.id) == st.session_state.editing_project_id),
            None,
        )
        if editing_project:
            _render_edit_dialog(editing_project)
            st.divider()

    # Handle delete confirmation
    if st.session_state.deleting_project_id:
        deleting_project = next(
            (p for p in projects if str(p.id) == st.session_state.deleting_project_id),
            None,
        )
        if deleting_project:
            _render_delete_confirmation(deleting_project)
            st.divider()

    # Render project cards
    for index, project in enumerate(projects):
        # Skip if currently editing or deleting
        if (st.session_state.editing_project_id == str(project.id) or
            st.session_state.deleting_project_id == str(project.id)):
            continue
        _render_project_card(project, index)

    # Navigation links
    st.markdown("---")
    st.markdown("### 快速导航")
    link_cols = st.columns(3)
    with link_cols[0]:
        st.page_link(get_app_page("home"), label="返回首页", icon="🏠")
    with link_cols[1]:
        st.page_link(get_app_page("project-mission"), label="开始新任务", icon="🧭")
    with link_cols[2]:
        st.page_link(get_app_page("workspace"), label="进入工作台", icon="📁")
