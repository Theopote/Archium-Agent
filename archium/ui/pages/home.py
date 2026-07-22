"""Archium home / overview page."""

from __future__ import annotations

import streamlit as st

from archium.ui.app_navigation import get_app_page
from archium.ui.product_flow import (
    primary_stages,
    product_flow_chain,
    product_flow_home_steps,
)


def render() -> None:
    stages = primary_stages()
    steps = product_flow_home_steps()
    numbered = "\n".join(f"{index}. {line}" for index, line in enumerate(steps, start=1))

    st.markdown("### 欢迎使用 Archium")
    st.markdown(
        f"""
Archium（阿基姆）面向建筑师与规划师，帮助你将项目资料组织为**可追溯、可编辑、可审核**的汇报材料。

**推荐主流程（5 步）：{product_flow_chain()}**

{numbered}

侧栏按 **项目 / 制作 / 资源 / 系统** 组织：日常在「制作」五阶段推进；用「项目」管理项目列表；模板能力在「资源 → 模板库」；系统设置在「设置」。
"""
    )

    st.markdown("#### 快速开始")
    link_cols = st.columns(6)
    with link_cols[0]:
        st.page_link(get_app_page("project-management"), label="项目", icon="📁")
    for column, stage in zip(link_cols[1:], stages, strict=True):
        with column:
            st.page_link(get_app_page(stage.page_key), label=stage.title, icon=stage.icon)

    st.markdown("#### 阶段说明")
    info_cols = st.columns(5)
    for column, stage in zip(info_cols, stages, strict=True):
        with column:
            st.info(f"{stage.icon} **{stage.title}**\n\n{stage.caption}")
