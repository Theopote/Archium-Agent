"""Global navigation components for consistent user orientation."""

from __future__ import annotations

import html
from typing import Literal

import streamlit as st


# 五阶段定义
FIVE_STAGES = [
    ("materials", "资料"),
    ("outline", "大纲"),
    ("generate", "生成"),
    ("edit", "编辑"),
    ("deliver", "交付"),
]


def render_workflow_progress_indicator(current_stage: str | None = None) -> None:
    """渲染五阶段进度指示器。

    Args:
        current_stage: 当前阶段的 key (materials/outline/generate/edit/deliver)
    """
    if current_stage is None:
        return

    stage_keys = [key for key, _ in FIVE_STAGES]

    try:
        current_index = stage_keys.index(current_stage)
    except ValueError:
        current_index = -1

    # 构建进度条 HTML
    progress_html = '<div style="display: flex; align-items: center; gap: 0.25rem; margin: 1rem 0; padding: 0.75rem; background: #f9fafb; border-radius: 0.5rem;">'

    for i, (key, label) in enumerate(FIVE_STAGES):
        # 确定状态
        if i < current_index:
            # 已完成
            color = "#10b981"
            bg_color = "#d1fae5"
            icon = "✓"
            font_weight = "400"
        elif i == current_index:
            # 当前阶段
            color = "#ffffff"
            bg_color = "#3b82f6"
            icon = "●"
            font_weight = "600"
        else:
            # 未开始
            color = "#9ca3af"
            bg_color = "#e5e7eb"
            icon = "○"
            font_weight = "400"

        progress_html += (
            f'<div style="flex: 1; text-align: center; padding: 0.5rem; '
            f'background: {bg_color}; border-radius: 0.375rem; transition: all 0.2s;">'
            f'<div style="color: {color}; font-size: 1.25rem; margin-bottom: 0.25rem;">{icon}</div>'
            f'<div style="color: {color}; font-size: 0.75rem; font-weight: {font_weight};">'
            f'{html.escape(label)}'
            f'</div>'
            f'</div>'
        )

        # 添加箭头（除了最后一个）
        if i < len(FIVE_STAGES) - 1:
            arrow_color = "#d1d5db" if i >= current_index else "#10b981"
            progress_html += f'<div style="color: {arrow_color}; font-size: 1rem;">→</div>'

    progress_html += '</div>'

    st.markdown(progress_html, unsafe_allow_html=True)


def render_contextual_breadcrumb(
    project_name: str | None = None,
    current_page: str | None = None,
) -> None:
    """渲染上下文感知的面包屑导航。

    Args:
        project_name: 当前项目名称
        current_page: 当前页面名称
    """
    parts = []

    # 首页链接
    parts.append('<a href="/" style="color: #6b7280; text-decoration: none;">首页</a>')

    # 项目名称
    if project_name:
        parts.append('<span style="color: #d1d5db; margin: 0 0.5rem;"> / </span>')
        parts.append(f'<span style="color: #1f2937; font-weight: 500;">{html.escape(project_name)}</span>')

    # 当前页面
    if current_page:
        parts.append('<span style="color: #d1d5db; margin: 0 0.5rem;"> / </span>')
        parts.append(f'<span style="color: #1f2937; font-weight: 600;">{html.escape(current_page)}</span>')

    breadcrumb_html = (
        f'<div style="margin-bottom: 1rem; padding: 0.5rem 0; font-size: 0.875rem; border-bottom: 1px solid #e5e7eb;">'
        f'{"".join(parts)}'
        f'</div>'
    )

    st.markdown(breadcrumb_html, unsafe_allow_html=True)


def render_quick_navigation_panel() -> None:
    """渲染快速导航面板 - 在侧边栏显示。"""
    from archium.ui.app_navigation import get_app_page

    st.markdown("### 快速导航")

    # 主要工作流
    st.markdown("**工作流程**")
    for key, label in FIVE_STAGES:
        st.page_link(get_app_page(key), label=f"📋 {label}")

    st.divider()

    # 项目管理
    st.markdown("**项目**")
    st.page_link(get_app_page("home"), label="🏠 首页")
    st.page_link(get_app_page("project-management"), label="📁 项目管理")
    st.page_link(get_app_page("project-genesis"), label="✨ 创建项目")

    st.divider()

    # 工具
    st.markdown("**工具**")
    st.page_link(get_app_page("tool-hub"), label="🧰 工具台")
    st.page_link(get_app_page("workspace"), label="⚙️ 完整工作台")


def get_stage_suggestion(current_stage: str) -> str | None:
    """根据当前阶段返回下一步建议。

    Args:
        current_stage: 当前阶段 key

    Returns:
        建议文本，如果没有建议则返回 None
    """
    suggestions = {
        "materials": "上传资料后，前往「大纲」规划汇报结构",
        "outline": "确认大纲后，前往「生成」开始产出页面内容",
        "generate": "页面生成完成后，前往「编辑」调整版式",
        "edit": "编辑完成后，前往「交付」导出最终文件",
        "deliver": "导出完成！可以返回「编辑」继续优化",
    }

    return suggestions.get(current_stage)


def render_stage_navigation_hint(current_stage: str) -> None:
    """渲染阶段导航提示。

    Args:
        current_stage: 当前阶段 key
    """
    suggestion = get_stage_suggestion(current_stage)

    if not suggestion:
        return

    st.info(f"💡 **下一步建议**: {suggestion}")


def get_current_stage_from_session() -> str | None:
    """从 session state 获取当前阶段。"""
    # 尝试从不同的 session key 推断当前阶段
    if st.session_state.get("current_flow_stage"):
        return st.session_state.current_flow_stage

    # 可以根据当前页面路径推断
    # 这里返回 None，让调用者显式传入
    return None


def set_current_stage(stage: str) -> None:
    """设置当前工作流阶段到 session。

    Args:
        stage: 阶段 key (materials/outline/generate/edit/deliver)
    """
    st.session_state.current_flow_stage = stage
