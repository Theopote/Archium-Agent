"""Right-hand properties panel for Presentation Studio."""

from __future__ import annotations

import streamlit as st

from archium.ui.label_map import entity_label, field_label
from archium.ui.layout_family_ui import format_layout_family_label, layout_family_implemented
from archium.ui.studio_service import SlideVisualSnapshot


def render_slide_properties(*, slide_snapshot: SlideVisualSnapshot | None, advanced: bool) -> None:
    """Render user-language slide properties."""
    st.markdown("**页面属性**")
    if slide_snapshot is None:
        st.caption("暂无选中页面。")
        return

    intent = slide_snapshot.visual_intent
    plan = slide_snapshot.layout_plan

    st.markdown(f"**{entity_label('VisualIntent', advanced=advanced)}**")
    if intent is None:
        st.caption("尚未生成页面视觉意图。请运行视觉编排。")
    else:
        st.write(f"{field_label('communication_goal', advanced=advanced)}：{intent.communication_goal}")
        st.write(f"{field_label('audience_takeaway', advanced=advanced)}：{intent.audience_takeaway}")
        st.write(f"{field_label('dominant_content_type', advanced=advanced)}：`{intent.dominant_content_type.value}`")
        st.write(f"{field_label('density_level', advanced=advanced)}：`{intent.density_level.value}`")

    st.markdown(f"**{entity_label('LayoutPlan', advanced=advanced)}**")
    if plan is None:
        st.caption("尚未生成页面版式。")
    else:
        st.write(f"{field_label('layout_family', advanced=advanced)}：{format_layout_family_label(plan.layout_family)}")
        if not layout_family_implemented(plan.layout_family):
            st.caption("该版式类型尚未实现导出器。")
        st.write(f"{field_label('layout_variant', advanced=advanced)}：`{plan.layout_variant}`")
        st.write(f"{field_label('whitespace_ratio', advanced=advanced)}：{plan.whitespace_ratio:.0%}")
        st.write(f"元素数：{len(plan.elements)}")
        if slide_snapshot.validation is not None:
            validation = slide_snapshot.validation
            st.write(
                f"版式质量：{validation.score:.2f} · "
                f"{'通过' if validation.valid else '需修复'}"
            )
            if validation.issues:
                with st.expander("版式问题", expanded=not validation.valid):
                    for issue in validation.issues[:6]:
                        st.write(f"- {issue.severity.value} · {issue.message}")

    if slide_snapshot.visual_critic is not None:
        critic = slide_snapshot.visual_critic
        total = critic.get("total_score")
        score_label = f"{total:.2f}" if isinstance(total, (int, float)) else "—"
        st.markdown(f"**{entity_label('Visual Critic', advanced=advanced)}**")
        st.write(f"评分：{score_label}")
