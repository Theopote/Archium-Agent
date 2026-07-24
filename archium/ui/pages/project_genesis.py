"""Project genesis — dual entry for concept exploration vs existing projects."""

from __future__ import annotations

import streamlit as st

from archium.application.project_management_service import ProjectManagementService
from archium.domain.enums import ProjectOriginMode
from archium.exceptions import ValidationError
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.components.chrome import render_page_header
from archium.ui.error_handlers import report_user_error


def render() -> None:
    """Let users start from an idea or from existing project materials."""
    render_page_header(
        "开始项目",
        "从一句话想法探索设计使命，或从已有资料整理汇报。",
    )

    tab_concept, tab_existing = st.tabs(["从想法开始", "从已有资料开始"])

    with tab_concept:
        _render_concept_form()

    with tab_existing:
        _render_existing_form()


def _render_concept_form() -> None:
    st.markdown("**概念探索** — 无需上传资料，先建立设计使命与假设。")
    with st.form("genesis_concept_form"):
        name = st.text_input("项目名称", placeholder="例如：黄土高原文化中心")
        idea = st.text_area(
            "一句话想法",
            placeholder="例如：我想在陕西关中乡村做一个面向游客和村民的小型书店",
            height=120,
        )
        submit = st.form_submit_button("创建并进入项目任务", type="primary", use_container_width=True)
        if submit:
            if not name.strip():
                st.error("请填写项目名称")
                return
            if not idea.strip():
                st.error("请用一句话描述你的想法")
                return
            try:
                with get_session() as session:
                    project = ProjectManagementService(session).create_project(
                        name.strip(),
                        idea.strip(),
                        origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
                    )
                st.session_state.selected_project_id = str(project.id)
                st.session_state.genesis_task_description = idea.strip()
                st.session_state.mission_step = 1
                st.switch_page(get_app_page("project-mission"))
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))


def _render_existing_form() -> None:
    st.markdown("**已有项目** — 上传 PDF、图纸、照片等资料 enrich 任务理解。")
    with st.form("genesis_existing_form"):
        name = st.text_input("项目名称", placeholder="例如：陕西省人民医院改造汇报")
        description = st.text_area("项目背景（可选）", height=80)
        submit = st.form_submit_button("创建并进入资料", type="primary", use_container_width=True)
        if submit:
            if not name.strip():
                st.error("请填写项目名称")
                return
            try:
                with get_session() as session:
                    project = ProjectManagementService(session).create_project(
                        name.strip(),
                        description.strip() or None,
                        origin_mode=ProjectOriginMode.EXISTING_PROJECT,
                    )
                st.session_state.selected_project_id = str(project.id)
                st.switch_page(get_app_page("materials"))
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))
