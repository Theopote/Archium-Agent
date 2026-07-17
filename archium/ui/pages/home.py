"""Archium home page."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    st.markdown("### 欢迎使用 Archium")
    st.markdown(
        """
Archium（阿基姆）面向建筑师与规划师，帮助你将项目资料组织为**可追溯、可编辑、可审核**的汇报材料。

**推荐工作流：**
1. 在 **项目工作台** 创建项目并导入 PDF / DOCX / PPTX 等资料
2. 填写汇报 Brief，运行 Brief → Storyline → SlideSpec 管线
3. 导出 JSON、Marp Markdown，或进一步导出 PPTX

**遗留能力：**
- **指令中心** 仍支持 v0.1 自然语言任务路由（快速 PPT、文件整理、Discord 守卫）
"""
    )

    col1, col2 = st.columns(2)
    with col1:
        st.info("📁 **项目工作台**\n\n结构化项目资料 + 多阶段汇报生成", icon="📁")
    with col2:
        st.info("💬 **指令中心**\n\n自然语言驱动 legacy 工具链", icon="💬")
