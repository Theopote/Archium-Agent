"""Enhanced UI components for Archium - consistent, reusable widgets."""

from __future__ import annotations

import html
from typing import Literal, Callable
from uuid import UUID

import streamlit as st

# Type definitions
StatusType = Literal["success", "info", "warning", "error", "pending"]
SizeType = Literal["small", "medium", "large"]


# ============================================================================
# Error Handling Components
# ============================================================================

def render_error_message(
    error: Exception | str,
    *,
    title: str = "操作失败",
    show_details: bool = True,
    action_label: str | None = None,
    on_action: Callable[[], None] | None = None,
) -> None:
    """统一的错误显示组件。

    Args:
        error: 错误对象或错误消息
        title: 错误标题
        show_details: 是否显示技术细节
        action_label: 操作按钮文字（如"重试"）
        on_action: 操作按钮回调
    """
    error_msg = str(error)

    # 用户友好的错误翻译
    friendly_msg = _translate_error(error_msg)

    st.error(f"**{title}**")
    st.markdown(friendly_msg)

    if show_details and error_msg != friendly_msg:
        with st.expander("技术细节", expanded=False):
            st.code(error_msg, language="text")

    if action_label and on_action:
        if st.button(action_label, key=f"error_action_{hash(error_msg)}"):
            on_action()


def _translate_error(error_msg: str) -> str:
    """将技术错误消息翻译为用户友好的语言。"""
    translations = {
        "ValidationError": "输入验证失败，请检查表单内容",
        "ProjectNotFoundError": "项目不存在或已被删除",
        "WorkflowError": "工作流执行出现问题",
        "ConnectionError": "网络连接失败，请检查网络设置",
        "TimeoutError": "操作超时，请稍后重试",
        "PermissionError": "权限不足",
    }

    for key, value in translations.items():
        if key in error_msg:
            return value

    return error_msg


# ============================================================================
# Progress & Status Components
# ============================================================================

def render_status_indicator(
    status: StatusType,
    label: str,
    *,
    show_icon: bool = True,
    size: SizeType = "medium",
) -> None:
    """状态指示器组件。

    Args:
        status: 状态类型
        label: 显示文本
        show_icon: 是否显示图标
        size: 大小
    """
    icons = {
        "success": "✅",
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "pending": "⏳",
    }

    colors = {
        "success": "#10b981",
        "info": "#3b82f6",
        "warning": "#f59e0b",
        "error": "#ef4444",
        "pending": "#6b7280",
    }

    icon = icons.get(status, "●") if show_icon else ""
    color = colors.get(status, "#6b7280")

    font_size = {"small": "0.875rem", "medium": "1rem", "large": "1.25rem"}[size]

    st.markdown(
        f'<div style="display: inline-flex; align-items: center; gap: 0.5rem; '
        f'color: {color}; font-size: {font_size};">'
        f'<span>{icon}</span>'
        f'<span>{html.escape(label)}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_progress_card(
    title: str,
    current: int,
    total: int,
    *,
    details: str | None = None,
    show_percentage: bool = True,
) -> None:
    """进度卡片组件。"""
    percentage = int((current / max(1, total)) * 100) if total > 0 else 0

    st.markdown(f"**{title}**")

    if show_percentage:
        st.caption(f"{current}/{total} 已完成 · {percentage}%")
    else:
        st.caption(f"{current}/{total} 已完成")

    st.progress(percentage / 100)

    if details:
        st.caption(details)


# ============================================================================
# Navigation Components
# ============================================================================

def render_breadcrumb(items: list[tuple[str, str | None]]) -> None:
    """面包屑导航组件。

    Args:
        items: [(label, page_key), ...] page_key 为 None 表示当前页
    """
    if not items:
        return

    parts = []
    for i, (label, page_key) in enumerate(items):
        if page_key is None or i == len(items) - 1:
            # 当前页
            parts.append(f'<span style="color: #1f2937; font-weight: 600;">{html.escape(label)}</span>')
        else:
            # 可点击的上级页面
            parts.append(f'<span style="color: #6b7280;">{html.escape(label)}</span>')

        if i < len(items) - 1:
            parts.append('<span style="color: #d1d5db; margin: 0 0.5rem;"> / </span>')

    st.markdown(
        f'<div style="margin-bottom: 1rem; font-size: 0.875rem;">'
        f'{"".join(parts)}'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_stage_progress_bar(
    stages: list[str],
    current_stage: str,
) -> None:
    """五阶段进度条组件。

    Args:
        stages: 阶段列表
        current_stage: 当前阶段
    """
    try:
        current_index = stages.index(current_stage)
    except ValueError:
        current_index = 0

    progress_html = '<div style="display: flex; gap: 0.5rem; margin: 1rem 0;">'

    for i, stage in enumerate(stages):
        if i < current_index:
            # 已完成
            color = "#10b981"
            icon = "✓"
        elif i == current_index:
            # 当前阶段
            color = "#3b82f6"
            icon = "●"
        else:
            # 未开始
            color = "#d1d5db"
            icon = "○"

        progress_html += (
            f'<div style="flex: 1; text-align: center;">'
            f'<div style="color: {color}; font-size: 1.5rem;">{icon}</div>'
            f'<div style="color: {color}; font-size: 0.75rem; margin-top: 0.25rem;">'
            f'{html.escape(stage)}'
            f'</div>'
            f'</div>'
        )

    progress_html += '</div>'

    st.markdown(progress_html, unsafe_allow_html=True)


# ============================================================================
# Action Cards
# ============================================================================

def render_action_card(
    title: str,
    description: str,
    *,
    icon: str = "📄",
    button_label: str = "开始",
    on_click: Callable[[], None] | None = None,
    disabled: bool = False,
    badge: str | None = None,
    key: str | None = None,
) -> None:
    """操作卡片组件 - 用于任务入口。"""
    with st.container(border=True):
        col1, col2 = st.columns([1, 4])

        with col1:
            st.markdown(
                f'<div style="font-size: 3rem; text-align: center;">{icon}</div>',
                unsafe_allow_html=True,
            )

        with col2:
            header_col, badge_col = st.columns([3, 1])
            with header_col:
                st.markdown(f"**{title}**")
            with badge_col:
                if badge:
                    st.markdown(
                        f'<span style="background: #3b82f6; color: white; '
                        f'padding: 0.25rem 0.5rem; border-radius: 0.25rem; '
                        f'font-size: 0.75rem;">{html.escape(badge)}</span>',
                        unsafe_allow_html=True,
                    )

            st.caption(description)

            if on_click:
                if st.button(
                    button_label,
                    key=key or f"action_{hash(title)}",
                    disabled=disabled,
                    use_container_width=True,
                ):
                    on_click()


# ============================================================================
# Empty States
# ============================================================================

def render_empty_state(
    title: str,
    description: str,
    *,
    icon: str = "📭",
    action_label: str | None = None,
    on_action: Callable[[], None] | None = None,
) -> None:
    """空状态组件 - 当列表为空时显示。"""
    st.markdown(
        f'<div style="text-align: center; padding: 3rem 1rem; color: #6b7280;">'
        f'<div style="font-size: 4rem; margin-bottom: 1rem;">{icon}</div>'
        f'<div style="font-size: 1.25rem; font-weight: 600; margin-bottom: 0.5rem; color: #1f2937;">'
        f'{html.escape(title)}'
        f'</div>'
        f'<div style="font-size: 0.875rem;">{html.escape(description)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if action_label and on_action:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button(action_label, use_container_width=True, type="primary"):
                on_action()


# ============================================================================
# Quick Info Components
# ============================================================================

def render_info_tooltip(text: str, *, tooltip: str) -> None:
    """带提示的信息文本。"""
    st.markdown(
        f'<span title="{html.escape(tooltip)}" style="cursor: help; '
        f'border-bottom: 1px dotted #6b7280;">'
        f'{html.escape(text)}'
        f'</span>',
        unsafe_allow_html=True,
    )


def render_quick_stats(stats: dict[str, str | int]) -> None:
    """快速统计数据显示。"""
    cols = st.columns(len(stats))

    for col, (label, value) in zip(cols, stats.items()):
        with col:
            st.metric(label=label, value=value)
