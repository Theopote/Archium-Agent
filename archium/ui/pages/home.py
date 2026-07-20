"""Archium home page."""

from __future__ import annotations

import streamlit as st

from archium.ui.app_navigation import get_app_page
from archium.ui.product_flow import (
    product_flow_chain,
    product_flow_home_steps,
    primary_stages,
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

日常请按主流程推进；「项目工作台 / 视觉设计 / 项目任务」等已收入侧栏 **进阶**，需要时再打开。
"""
    )

    st.markdown("#### 快速开始")
    link_cols = st.columns(5)
    for column, stage in zip(link_cols, stages, strict=True):
        with column:
            st.page_link(get_app_page(stage.page_key), label=stage.title, icon=stage.icon)

    st.markdown("#### 阶段说明")
    info_cols = st.columns(5)
    for column, stage in zip(info_cols, stages, strict=True):
        with column:
            st.info(f"{stage.icon} **{stage.title}**\n\n{stage.caption}")
