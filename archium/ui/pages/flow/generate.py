"""Product-flow stage: 生成."""

from __future__ import annotations

import streamlit as st

from archium.ui.app_navigation import get_app_page
from archium.ui.pages.flow import render_stage_header, render_stage_nav
from archium.ui.pages.workspace import render_generate_stage, render_project_picker


def render() -> None:
    render_stage_header("generate")
    st.info(
        "生成页面内容与管线结果。"
        "版式微调请到「编辑」；导出 PPTX/PDF 请到「交付」。"
    )
    project_id = render_project_picker(allow_create=False)
    if project_id is None:
        st.info("请先在「资料」阶段创建或选择项目。")
        render_stage_nav("generate")
        return
    render_generate_stage(project_id, include_export=False)
    st.divider()
    link_cols = st.columns(2)
    with link_cols[0]:
        st.page_link(get_app_page("edit"), label="前往编辑（汇报工作室）", icon="🎬")
    with link_cols[1]:
        st.page_link(get_app_page("deliver"), label="前往交付与导出", icon="📦")
    render_stage_nav("generate")
