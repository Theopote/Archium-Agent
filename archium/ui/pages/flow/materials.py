"""Product-flow stage: 资料."""

from __future__ import annotations

import streamlit as st

from archium.ui.pages.flow import render_stage_header, render_stage_nav
from archium.ui.pages.workspace import render_materials_stage, render_project_picker


def render() -> None:
    render_stage_header("materials")
    project_id = render_project_picker(allow_create=True)
    if project_id is None:
        st.info("创建或选择项目后，即可上传资料并整理事实与素材。")
        render_stage_nav("materials")
        return
    render_materials_stage(project_id)
    st.divider()
    render_stage_nav("materials")
