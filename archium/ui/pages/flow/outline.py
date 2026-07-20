"""Product-flow stage: 大纲."""

from __future__ import annotations

import streamlit as st

from archium.ui.pages import project_mission
from archium.ui.pages.flow import render_stage_header, render_stage_nav


def render() -> None:
    render_stage_header("outline")
    st.info(
        "在本阶段描述汇报任务并确认结构。"
        "完成后进入「生成」产出页面内容；完整规划工具仍可在进阶「项目任务」中打开。"
    )
    project_mission.render()
    st.divider()
    render_stage_nav("outline")
