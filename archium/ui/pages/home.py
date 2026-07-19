"""Archium home page."""

from __future__ import annotations

import streamlit as st

from archium.ui.app_navigation import get_app_page
from archium.ui.label_map import content_pipeline_chain, entity_label


def render() -> None:
    pipeline = content_pipeline_chain()
    st.markdown("### 欢迎使用 Archium")
    st.markdown(
        f"""
Archium（阿基姆）面向建筑师与规划师，帮助你将项目资料组织为**可追溯、可编辑、可审核**的汇报材料。

**推荐主流程（9 步）：**
1. **创建项目** — 在工作台新建项目并上传资料
2. **上传资料** — PDF、Word、图纸说明等
3. **描述汇报任务** — 在「项目任务」用一句话说明要做什么汇报
4. **确认系统理解** — 核对「{entity_label("ProjectMission")}」，补充「{entity_label("KnowledgeGap")}」
5. **确认汇报结构** — 审核「{entity_label("Storyline")}」与「{entity_label("PresentationBrief")}」
6. **选择视觉方向** — 确认「{entity_label("ArtDirection")}」（可选：在「视觉设计」精细挑选）
7. **生成整套汇报** — 产出「{entity_label("SlideSpec")}」与「{entity_label("LayoutPlan")}」
8. **在汇报工作室修改** — 预览、内容适配、AI 编辑、撤销
9. **导出 PowerPoint** — 交付可编辑 PPTX

日常编辑请优先进入 **汇报工作室**；项目工作台负责资料与内容生成，视觉设计保留为进阶入口。

若目标已明确，可跳过项目任务，直接在工作台填写「{entity_label("PresentationBrief")}」并生成内容。
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
        st.info("🧭 **项目任务**\n\n描述任务 → 澄清 → 规划成果", icon="🧭")
    with col2:
        st.info(f"📁 **项目工作台**\n\n资料 + {pipeline}", icon="📁")
    with col3:
        st.info("🎬 **汇报工作室**\n\n预览 + 编辑 + 导出", icon="🎬")
    with col4:
        st.info(f"🎨 **视觉设计**\n\n{entity_label('ArtDirection')} + 版式候选", icon="🎨")
    with col5:
        st.info("💬 **指令中心**\n\n自然语言快捷工具", icon="💬")
