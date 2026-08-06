"""Studio 布局增强 - 快捷键提示和操作面板。"""

from __future__ import annotations

import streamlit as st


def render_studio_shortcuts_panel() -> None:
    """渲染 Studio 快捷键提示面板。"""
    with st.expander("⌨️ 快捷键", expanded=False):
        st.markdown("""
        ### 导航快捷键
        - **Tab**: 切换检查器标签
        - **←/→**: 上一页/下一页
        - **Esc**: 退出全屏模式

        ### 编辑快捷键（即将支持）
        - **Ctrl+S**: 保存当前修改
        - **Ctrl+Z**: 撤销
        - **Ctrl+Y**: 重做
        - **Ctrl+D**: 复制当前页

        ### 视图快捷键（即将支持）
        - **Ctrl+0**: 重置缩放
        - **Ctrl++**: 放大画布
        - **Ctrl+-**: 缩小画布
        """)


def render_studio_zoom_controls() -> None:
    """渲染画布缩放控制。"""
    zoom_level = st.session_state.get("studio_zoom_level", 100)

    cols = st.columns([1, 2, 1])

    with cols[0]:
        if st.button("➖", key="zoom_out", help="缩小（Ctrl+-）"):
            zoom_level = max(25, zoom_level - 25)
            st.session_state.studio_zoom_level = zoom_level
            st.rerun()

    with cols[1]:
        new_zoom = st.slider(
            "缩放",
            min_value=25,
            max_value=200,
            value=zoom_level,
            step=25,
            key="zoom_slider",
            label_visibility="collapsed",
        )
        if new_zoom != zoom_level:
            st.session_state.studio_zoom_level = new_zoom
            st.rerun()

    with cols[2]:
        if st.button("➕", key="zoom_in", help="放大（Ctrl++）"):
            zoom_level = min(200, zoom_level + 25)
            st.session_state.studio_zoom_level = zoom_level
            st.rerun()

    st.caption(f"当前缩放: {zoom_level}%")


def render_studio_quick_actions(
    *,
    slide_snapshot,
    presentation_id,
) -> None:
    """渲染快速操作面板。"""
    from archium.ui.components.enhanced_ui import render_action_card

    st.markdown("### 快速操作")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📋 复制页面", key="quick_copy", use_container_width=True):
            st.info("复制功能即将实现")

        if st.button("🗑️ 删除页面", key="quick_delete", use_container_width=True):
            st.warning("删除功能需确认")

    with col2:
        if st.button("↕️ 移动页面", key="quick_move", use_container_width=True):
            st.info("移动功能即将实现")

        if st.button("🔄 刷新预览", key="quick_refresh", use_container_width=True):
            st.rerun()


def render_studio_status_bar(
    *,
    current_page: int,
    total_pages: int,
    unsaved_changes: bool = False,
) -> None:
    """渲染 Studio 底部状态栏。"""
    from archium.ui.components.enhanced_ui import render_status_indicator

    cols = st.columns([2, 1, 1])

    with cols[0]:
        st.caption(f"第 {current_page + 1} 页 / 共 {total_pages} 页")

    with cols[1]:
        if unsaved_changes:
            render_status_indicator("warning", "有未保存修改", size="small")
        else:
            render_status_indicator("success", "已保存", size="small")

    with cols[2]:
        st.caption(f"缩放: {st.session_state.get('studio_zoom_level', 100)}%")


def render_inspector_help_hints(active_tab: str) -> None:
    """根据当前检查器标签显示上下文帮助。"""
    hints = {
        "属性": "💡 **提示**: 在这里修改页面标题、内容和基本属性。",
        "布局": "💡 **提示**: 选择不同的版式布局，系统会自动适配内容。",
        "内容": "💡 **提示**: 调整文本内容、资产绑定和证据引用。",
        "修改": "💡 **提示**: 使用 AI 辅助修改页面内容和布局。",
        "评论": "💡 **提示**: 查看和回复团队成员的评论。",
        "风格": "💡 **提示**: 设置汇报的整体气质和视觉风格。",
        "设计系统": "💡 **提示**: 应用专业模板和优化布局质量。",
    }

    hint = hints.get(active_tab)
    if hint:
        st.info(hint)


def render_panel_width_control() -> int:
    """渲染面板宽度控制，返回当前宽度百分比。"""
    width_options = {
        "窄": 20,
        "中": 30,
        "宽": 40,
    }

    selected = st.radio(
        "面板宽度",
        options=list(width_options.keys()),
        horizontal=True,
        key="inspector_width",
        label_visibility="collapsed",
    )

    return width_options.get(selected, 30)
