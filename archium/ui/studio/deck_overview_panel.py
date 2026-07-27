"""Deck Overview — full-deck grid with narrative role coloring."""

from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

from archium.domain.slide_role import SlideRole
from archium.ui.label_map import slide_role_label
from archium.ui.page_status_board_panel import status_badge
from archium.ui.studio.deck_content_placeholder import content_placeholder_html
from archium.ui.studio.slide_navigator import _set_selected_slide, _status_by_slide
from archium.ui.studio_service import StudioPresentationContext


_ROLE_COLORS: dict[SlideRole, str] = {
    SlideRole.OPENING: "#b8860b",
    SlideRole.BACKGROUND: "#667085",
    SlideRole.QUESTION: "#d92d20",
    SlideRole.VISION: "#7a5af8",
    SlideRole.CONCLUSION: "#b8860b",
    SlideRole.SITE_ANALYSIS: "#175cd3",
    SlideRole.CONTEXT_ANALYSIS: "#175cd3",
    SlideRole.PROBLEM_ANALYSIS: "#d92d20",
    SlideRole.CONCEPT: "#7a5af8",
    SlideRole.STRATEGY: "#12b76a",
    SlideRole.SPATIAL_LOGIC: "#12b76a",
    SlideRole.FORM: "#7a5af8",
    SlideRole.MATERIAL: "#667085",
    SlideRole.EXPERIENCE: "#7a5af8",
    SlideRole.CASE_STUDY: "#175cd3",
    SlideRole.COMPARISON: "#f79009",
    SlideRole.DATA: "#175cd3",
    SlideRole.SUMMARY: "#667085",
    SlideRole.TIMELINE: "#667085",
    SlideRole.IMPLEMENTATION: "#667085",
    SlideRole.OTHER: "#98a2b3",
}


def role_color(role: SlideRole | None) -> str:
    if role is None:
        return "#98a2b3"
    return _ROLE_COLORS.get(role, "#98a2b3")


def render_deck_overview(
    *,
    context: StudioPresentationContext,
    key_prefix: str = "deck_overview",
) -> None:
    """Grid thumbnail overview with story-role color band."""
    slides = context.snapshot.slides
    if not slides:
        st.caption("当前汇报还没有页面。")
        return

    status_map = _status_by_slide(context)
    st.markdown("**全稿鸟瞰**")
    st.caption(
        "按页角色着色："
        "蓝=分析 · 红=问题 · 绿=策略 · 金=开篇/收尾 · 紫=概念/体验"
    )

    cols_per_row = 4
    for row_start in range(0, len(slides), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_index, item in enumerate(slides[row_start : row_start + cols_per_row]):
            index = row_start + col_index
            slide = item.slide
            role = getattr(slide, "slide_role", None)
            color = role_color(role)
            role_label = slide_role_label(role)
            title = (slide.title or "未命名").strip()
            preview_path = item.preview_image
            has_preview = bool(preview_path and Path(preview_path).is_file())
            row = status_map.get(str(slide.id))
            badge = status_badge(row) if row is not None else ""

            with cols[col_index]:
                card_key = f"{key_prefix}_card_{context.presentation.id}_{index}"
                if st.button(
                    f"P{index + 1} · {title[:18]}",
                    key=card_key,
                    use_container_width=True,
                ):
                    _set_selected_slide(index)
                    st.session_state.studio_center_mode = "edit"
                    st.rerun()

                if has_preview and preview_path is not None:
                    st.image(preview_path, use_container_width=True)
                else:
                    st.markdown(
                        content_placeholder_html(
                            index=index,
                            slide=slide,
                            accent_color=color,
                        ),
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    f'<div style="height:4px;background:{html.escape(color)};border-radius:2px;'
                    f'margin:0.25rem 0;"></div>'
                    f'<div style="font-size:0.75rem;color:#5a5248;">{html.escape(role_label)}'
                    f'{(" · " + html.escape(badge)) if badge else ""}</div>',
                    unsafe_allow_html=True,
                )
