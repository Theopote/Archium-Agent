"""Archium home page."""

from __future__ import annotations

import streamlit as st

from archium.ui.app_navigation import get_app_page


def render() -> None:
    st.markdown("### 欢迎使用 Archium")
    st.markdown(
        """
Archium（阿基姆）面向建筑师与规划师，帮助你将项目资料组织为**可追溯、可编辑、可审核**的汇报材料。

**推荐主流程（9 步）：**
1. **设置** — 配置 AI 服务商与 API Key（或使用 `.env`）
2. **项目任务** — 用自然语言描述任务，澄清需求并规划成果（从模糊需求起步的推荐入口）
3. **项目工作台** — 导入资料，生成并审核「汇报简报 → 叙事结构 → 页面内容」
4. **汇报工作室** — 浏览全部页面、生成版式、内容微调与导出 PPTX / PDF（**日常主编辑入口**）
5. 逐页检查版式质量与整套一致性
6. 按需使用内容适配（改文字结构）或 AI 编辑（改版式表现）
7. 导出 PowerPoint 或 PDF 交付
8. （可选）**视觉设计** — 审核视觉方向、在候选版式间精细挑选
9. （可选）**指令中心** — v0.1 自然语言任务路由（快速 PPT、文件整理）

若目标已明确，可跳过项目任务，直接在工作台填写简报并生成内容。
"""
    )

    st.markdown("#### 快速开始")
    link_cols = st.columns(3)
    with link_cols[0]:
        st.page_link(get_app_page("project-mission"), label="从任务描述开始", icon="🧭")
    with link_cols[1]:
        st.page_link(get_app_page("workspace"), label="进入项目工作台", icon="📁")
    with link_cols[2]:
        st.page_link(get_app_page("studio"), label="打开汇报工作室", icon="🎬")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.info("🧭 **项目任务**\n\n模糊描述 → 澄清 → 规划成果", icon="🧭")
    with col2:
        st.info("📁 **项目工作台**\n\n资料管理 + 生成 / 审核 / 导出", icon="📁")
    with col3:
        st.info("🎬 **汇报工作室**\n\n三栏预览 + 版式属性 + 导出", icon="🎬")
    with col4:
        st.info("🎨 **视觉设计**\n\n视觉方向 + 版式候选 / 批准", icon="🎨")
    with col5:
        st.info("💬 **指令中心**\n\n自然语言驱动 legacy 工具链", icon="💬")
