"""Slide list navigation for Presentation Studio."""

from __future__ import annotations

import streamlit as st

from archium.ui.layout_family_ui import format_layout_family_label
from archium.ui.studio_service import StudioPresentationContext, get_selected_slide_snapshot


def render_slide_navigator(*, context: StudioPresentationContext) -> int:
    """Render slide thumbnails/list and return the selected slide index."""
    st.markdown("**页面导航**")
    slides = context.snapshot.slides
    if not slides:
        st.caption("当前汇报还没有页面。")
        return 0

    selected_index = int(st.session_state.get("studio_selected_slide_index", 0))
    selected_index = max(0, min(selected_index, len(slides) - 1))

    for index, item in enumerate(slides):
        slide = item.slide
        plan = item.layout_plan
        family = format_layout_family_label(plan.layout_family) if plan else "待生成版式"
        valid = item.validation.valid if item.validation is not None else None
        status_icon = "✅" if valid else ("⚠️" if valid is False else "○")
        label = f"P{slide.order + 1} · {slide.title[:24]}"
        if st.button(
            f"{status_icon} {label}",
            key=f"studio_nav_slide_{context.presentation.id}_{index}",
            use_container_width=True,
            type="primary" if index == selected_index else "secondary",
        ):
            st.session_state.studio_selected_slide_index = index
            selected_index = index

    st.session_state.studio_selected_slide_index = selected_index
    current = get_selected_slide_snapshot(context, selected_index)
    if current is not None:
        st.caption(f"当前：P{current.slide.order + 1} · {family}")
    return selected_index
