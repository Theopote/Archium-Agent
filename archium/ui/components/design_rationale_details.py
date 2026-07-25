"""Render DesignRationale in Streamlit."""

from __future__ import annotations

import streamlit as st

from archium.domain.design_rationale import DesignRationale


def render_design_rationale(
    rationale: DesignRationale | None,
    *,
    expanded: bool = True,
) -> None:
    if rationale is None or rationale.is_empty():
        return
    with st.expander("设计推理", expanded=expanded):
        if rationale.statement.strip():
            st.markdown(f"**判断**：{rationale.statement.strip()}")
        if rationale.reasons:
            st.markdown("**理由**")
            for item in rationale.reasons:
                st.markdown(f"- {item}")
        if rationale.evidence:
            st.markdown("**依据**")
            for item in rationale.evidence:
                st.markdown(f"- {item}")
        if rationale.alternatives:
            st.markdown("**权衡 / 未选方案**")
            for alt in rationale.alternatives:
                if alt.note.strip():
                    st.markdown(f"- **{alt.label}**：{alt.note}")
                elif alt.label.strip():
                    st.markdown(f"- {alt.label}")
        if rationale.confidence > 0:
            st.caption(f"把握度约 {int(round(rationale.confidence * 100))}%")
