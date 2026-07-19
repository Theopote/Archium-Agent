"""Archium home page."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    st.markdown("### 欢迎使用 Archium")
    st.markdown(
        """
Archium（阿基姆）面向建筑师与规划师，帮助你将项目资料组织为**可追溯、可编辑、可审核**的汇报材料。

**推荐工作流：**
0. 在 **设置** 中配置 AI 服务商与 API Key（或使用 `.env`）
1. 在 **项目任务** 中自由描述任务，经澄清与路径规划后选定成果（从模糊需求起步的推荐入口）
2. 进入 **项目工作台**：导入资料、运行 Brief → Storyline → 页面内容 管线，审核并导出
3. 在审核面板编辑并批准 Brief / Storyline，再继续生成后续阶段
4. 进入 **汇报工作室**：浏览页面、查看版式、导出 PPTX（推荐主编辑入口）
5. 或使用 **视觉设计**：生成 ArtDirection 与 LayoutPlan，审核视觉方向并选择候选版式
6. 导出 JSON、Marp Markdown，或进一步导出 PPTX

**项目任务** 负责从模糊任务描述澄清到规划；**项目工作台** 是持续编辑、审核与导出的工作区；**汇报工作室** 是页面级预览与导出的主界面；**视觉设计** 负责深度视觉编排与候选版式调整。若目标已明确，也可跳过项目任务，直接在工作台填写 Brief。

**遗留能力：**
- **指令中心** 仍支持 v0.1 自然语言任务路由（快速 PPT、文件整理）
"""
    )

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
