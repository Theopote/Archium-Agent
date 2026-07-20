"""Center canvas preview for Presentation Studio."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from archium.domain.visual.enums import LayoutIssueSeverity
from archium.ui.label_map import entity_label, field_label
from archium.ui.layout_family_ui import format_layout_family_label
from archium.ui.studio.element_labels import format_element_label
from archium.ui.visual_service import SlideVisualSnapshot

_SEVERITY_COLORS = {
    LayoutIssueSeverity.CRITICAL: "#b42318",
    LayoutIssueSeverity.ERROR: "#d92d20",
    LayoutIssueSeverity.WARNING: "#b54708",
    LayoutIssueSeverity.INFO: "#175cd3",
}


def _preview_caption(kind: str | None) -> str:
    if kind == "scene":
        return "RenderScene 真实预览（Studio Canvas 视觉真相源）"
    if kind == "screenshot":
        return "PPTX 截图预览（来自最近一次视觉编排导出）"
    if kind == "wireframe":
        return "版式线框预览（由 LayoutPlan 几何自动生成；无 RenderScene 时的降级）"
    return "暂无预览。生成版式后将编译 RenderScene；必要时可降级为线框。"


def _render_validation_overlay(
    *,
    slide_snapshot: SlideVisualSnapshot,
    selected_element_id: str | None,
) -> None:
    validation = slide_snapshot.validation
    plan = slide_snapshot.layout_plan
    if validation is None or not validation.issues:
        return

    issue_element_ids: set[str] = set()
    for issue in validation.issues:
        issue_element_ids.update(issue.element_ids)

    st.markdown("**版式问题标注**")
    for issue in validation.issues[:8]:
        color = _SEVERITY_COLORS.get(issue.severity, "#667085")
        element_hint = ""
        if issue.element_ids:
            element_hint = f" · 元素 {', '.join(issue.element_ids[:3])}"
        st.markdown(
            f"<span style='color:{color};font-weight:600;'>{issue.severity.value}</span>"
            f" · {issue.message}{element_hint}",
            unsafe_allow_html=True,
        )

    if plan is None or not issue_element_ids:
        return

    width = float(plan.page_width or 10)
    height = float(plan.page_height or 5.625)
    boxes: list[str] = []
    for element in plan.elements:
        if element.id not in issue_element_ids and element.id != selected_element_id:
            continue
        left = max(0.0, element.x / width * 100)
        top = max(0.0, element.y / height * 100)
        box_width = max(1.0, element.width / width * 100)
        box_height = max(1.0, element.height / height * 100)
        if element.id == selected_element_id:
            border = "2px solid #175cd3"
            background = "rgba(23, 92, 211, 0.08)"
        else:
            border = "2px solid #d92d20"
            background = "rgba(217, 45, 32, 0.10)"
        boxes.append(
            "<div style="
            f"'position:absolute;left:{left:.2f}%;top:{top:.2f}%;"
            f"width:{box_width:.2f}%;height:{box_height:.2f}%;"
            f"border:{border};background:{background};border-radius:4px;'></div>"
        )
    if boxes:
        st.caption("线框标注：蓝框为当前元素，红框为问题元素")
        st.markdown(
            "<div style='position:relative;width:100%;aspect-ratio:16/9;"
            "background:#faf9f7;border:1px solid #eceae4;border-radius:8px;'>"
            + "".join(boxes)
            + "</div>",
            unsafe_allow_html=True,
        )


def render_slide_canvas(*, slide_snapshot: SlideVisualSnapshot | None, advanced: bool) -> None:
    """Render the selected slide preview area."""
    st.markdown("**页面预览**")
    if slide_snapshot is None:
        st.info("请选择左侧页面。")
        return

    slide = slide_snapshot.slide
    plan = slide_snapshot.layout_plan
    selected_element_id = st.session_state.get("studio_selected_element_id")
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

    _render_validation_overlay(
        slide_snapshot=slide_snapshot,
        selected_element_id=str(selected_element_id) if selected_element_id else None,
    )

    if plan is not None:
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
