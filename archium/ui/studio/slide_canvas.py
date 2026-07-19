"""Center canvas preview for Presentation Studio."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from archium.ui.label_map import entity_label, field_label
from archium.ui.layout_family_ui import format_layout_family_label
from archium.ui.studio.element_labels import format_element_label
from archium.ui.visual_service import SlideVisualSnapshot


def _preview_caption(kind: str | None) -> str:
    if kind == "screenshot":
        return "PPTX 截图预览（来自最近一次视觉编排导出）"
    if kind == "wireframe":
        return "版式线框预览（由 LayoutPlan 几何自动生成）"
    return "暂无预览。生成版式后将显示线框；导出 PPTX 后可显示截图。"


def render_slide_canvas(*, slide_snapshot: SlideVisualSnapshot | None, advanced: bool) -> None:
    """Render the selected slide preview area."""
    st.markdown("**页面预览**")
    if slide_snapshot is None:
        st.info("请选择左侧页面。")
        return

    slide = slide_snapshot.slide
    plan = slide_snapshot.layout_plan
    header_cols = st.columns([3, 1])
    with header_cols[0]:
        st.markdown(f"#### P{slide.order + 1} · {slide.title}")
        st.caption(slide.message or "（无核心信息）")
    with header_cols[1]:
        if slide_snapshot.validation is not None:
            valid = slide_snapshot.validation.valid
            st.metric(
                "版式质量",
                f"{slide_snapshot.validation.score:.2f}",
                delta="通过" if valid else "需修复",
                delta_color="normal" if valid else "inverse",
            )

    preview_path = slide_snapshot.preview_image
    if preview_path and Path(preview_path).is_file():
        st.image(preview_path, use_container_width=True)
        st.caption(_preview_caption(slide_snapshot.preview_kind))
    else:
        st.markdown(
            '<div style="border:1px dashed #d8d6d0;border-radius:8px;'
            'padding:3rem 1rem;text-align:center;color:#8a8780;background:#faf9f7;">'
            "暂无页面预览<br>"
            "<span style='font-size:0.85rem;'>请先生成版式，或运行带 PPTX 导出的视觉编排</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    if plan is not None:
        selected_element_id = st.session_state.get("studio_selected_element_id")
        highlight = ""
        if selected_element_id and plan.element_by_id(str(selected_element_id)) is not None:
            element = plan.element_by_id(str(selected_element_id))
            if element is not None:
                highlight = f" · 当前元素：{format_element_label(element_id=element.id, role=element.role)}"
        st.caption(
            f"版式：{format_layout_family_label(plan.layout_family)} · "
            f"变体 {plan.layout_variant} · 留白 {plan.whitespace_ratio:.0%}{highlight}"
        )

    with st.expander(entity_label("SlideSpec", advanced=advanced), expanded=False):
        st.write(f"{field_label('title', advanced=advanced)}：{slide.title}")
        st.write(f"{field_label('message', advanced=advanced)}：{slide.message or '—'}")
        st.write(f"状态：`{slide.status.value}`")
        if advanced:
            st.write(f"SlideSpec ID：`{slide.id}`")
