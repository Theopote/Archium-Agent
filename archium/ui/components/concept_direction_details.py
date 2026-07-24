"""Shared Streamlit rendering for ConceptDirection structured fields."""

from __future__ import annotations

import streamlit as st

from archium.domain.concept_direction import ConceptDirection


def render_concept_direction_details(direction: ConceptDirection) -> None:
    """Render narrative + structured spatial/form/visual fields."""
    if direction.theme:
        st.markdown(f"**主题**：{direction.theme}")
    if direction.summary:
        st.markdown(direction.summary)
    if direction.spatial_strategy:
        st.markdown(f"**空间策略**：{direction.spatial_strategy}")
    if direction.spatial_idea:
        st.markdown(f"**空间想法**：{direction.spatial_idea}")
    if direction.formal_language:
        st.markdown(f"**形式语言**：{direction.formal_language}")
    if direction.material_strategy:
        st.markdown(f"**材料策略**：{direction.material_strategy}")
    if direction.reference_dna:
        st.markdown("**参照基因**")
        for item in direction.reference_dna:
            st.markdown(f"- {item}")
    if direction.visual_prompt is not None and not direction.visual_prompt.is_empty():
        st.markdown("**视觉生成参数**")
        vp = direction.visual_prompt
        if vp.image_prompt:
            st.markdown(f"- 画面：{vp.image_prompt}")
        if vp.camera:
            st.markdown(f"- 视角：{vp.camera}")
        if vp.style:
            st.markdown(f"- 风格：{vp.style}")
    if direction.experience_focus:
        st.markdown(f"**体验焦点**：{direction.experience_focus}")
    if direction.differentiator:
        st.markdown(f"**差异点**：{direction.differentiator}")
    if direction.open_questions:
        st.markdown("**开放问题**")
        for item in direction.open_questions:
            st.markdown(f"- {item}")
    if direction.risks:
        st.markdown("**风险**")
        for item in direction.risks:
            st.markdown(f"- {item}")
