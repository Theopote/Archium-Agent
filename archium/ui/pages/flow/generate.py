"""Product-flow stage: 生成."""

from __future__ import annotations

import streamlit as st

from archium.ui.app_navigation import get_app_page
from archium.ui.pages.flow import render_stage_header, render_stage_nav
from archium.ui.pages.workspace import render_generate_stage, render_project_picker
from archium.ui.project_progress_card import load_project_progress_snapshot


def render() -> None:
    render_stage_header("generate")
    st.info("生成页面内容与管线结果。版式微调请到「工作室」。")
    project_id = render_project_picker(allow_create=False)
    if project_id is None:
        st.info("请先在「资料」阶段创建或选择项目。")
        render_stage_nav("generate")
        return
    render_generate_stage(project_id, include_export=False)

    snapshot = None
    try:
        snapshot = load_project_progress_snapshot()
    except Exception:
        snapshot = None
    if snapshot is not None and snapshot.ready_for_export:
        with st.expander("更多", expanded=False):
            st.page_link(get_app_page("deliver"), label="前往交付（版式已齐）", icon="📦")

    render_stage_nav("generate")
