"""AI natural-language edit panel stub for Presentation Studio."""

from __future__ import annotations

import streamlit as st


def render_ai_edit_panel(*, disabled: bool = True) -> None:
    """Render NL edit UI skeleton (Step 7 will wire intents + revision)."""
    st.markdown("**AI 编辑**")
    st.caption("用自然语言调整页面版式与内容（Step 7 启用）。")
    st.text_area(
        "描述你想做的修改",
        placeholder="例如：减少文字、放大主图、切换到图纸优先…",
        height=120,
        disabled=disabled,
        key="studio_ai_edit_input",
    )
    preset_rows = [
        [("减少文字", "reduce_text"), ("放大主图", "enlarge_hero")],
        [("增加留白", "more_whitespace"), ("图纸优先", "drawing_focus")],
    ]
    for row in preset_rows:
        cols = st.columns(2)
        for column, (label, action) in zip(cols, row, strict=True):
            column.button(
                label,
                disabled=disabled,
                use_container_width=True,
                key=f"studio_preset_{action}",
            )
    st.caption("预设与撤销将在 Step 7 接入 Revision 服务。")
