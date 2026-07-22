"""Product-flow stage: 资料 — 文件 | 事实 | 素材 | 缺口."""

from __future__ import annotations

import streamlit as st

from archium.ui.pages.flow import (
    render_flow_project_context,
    render_stage_header,
    render_stage_nav,
)
from archium.ui.pages.workspace import render_materials_stage


def render() -> None:
    render_stage_header("materials")
    st.caption("整理本项目资料。完整工作台能力在深层「项目工作台」页，日常不必打开。")
    project_id = render_flow_project_context(allow_create=True, key_prefix="materials")
    if project_id is None:
        st.info("创建或选择项目后，即可上传资料并整理事实与素材。")
        render_stage_nav("materials")
        return
    render_materials_stage(project_id)
    st.divider()
    render_stage_nav("materials")
