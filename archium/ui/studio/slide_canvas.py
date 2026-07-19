"""Center canvas preview for Presentation Studio."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from archium.ui.label_map import entity_label, field_label
from archium.ui.studio_service import SlideVisualSnapshot


def render_slide_canvas(*, slide_snapshot: SlideVisualSnapshot | None, advanced: bool) -> None:
    """Render the selected slide preview area."""
    st.markdown("**页面预览**")
    if slide_snapshot is None:
        st.info("请选择左侧页面。")
        return

    slide = slide_snapshot.slide
    st.markdown(f"#### P{slide.order + 1} · {slide.title}")
    st.caption(slide.message or "（无核心信息）")

    preview_path = slide_snapshot.preview_image
    if preview_path and Path(preview_path).is_file():
        st.image(preview_path, use_container_width=True)
        st.caption("预览图来自最近一次视觉编排导出。")
    else:
        st.markdown(
            '<div style="border:1px dashed #d8d6d0;border-radius:8px;'
            'padding:3rem 1rem;text-align:center;color:#8a8780;background:#faf9f7;">'
            "页面预览将在生成版式并导出后显示<br>"
            "<span style='font-size:0.85rem;'>Step 6 将完善缩略图导航与实时预览</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    with st.expander(entity_label("SlideSpec", advanced=advanced), expanded=False):
        st.write(f"{field_label('title', advanced=advanced)}：{slide.title}")
        st.write(f"{field_label('message', advanced=advanced)}：{slide.message or '—'}")
        st.write(f"状态：`{slide.status.value}`")
        if advanced:
            st.write(f"SlideSpec ID：`{slide.id}`")
