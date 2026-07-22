"""Shared chrome for product-flow stage pages."""

from __future__ import annotations

import streamlit as st

from archium.ui.app_navigation import get_app_page
from archium.ui.product_flow import get_stage, next_stage, previous_stage, product_flow_chain


def render_stage_header(stage_id: str) -> None:
    stage = get_stage(stage_id)
    st.markdown(f"### {stage.title}")
    st.caption(stage.caption)
    st.caption(f"制作流程：{product_flow_chain()}")


def render_stage_nav(stage_id: str) -> None:
    """Previous / next stage links."""
    prev = previous_stage(stage_id)
    nxt = next_stage(stage_id)
    cols = st.columns(2)
    with cols[0]:
        if prev is not None:
            st.page_link(
                get_app_page(prev.page_key),
                label=f"← 上一阶段：{prev.title}",
                icon=prev.icon,
            )
    with cols[1]:
        if nxt is not None:
            st.page_link(
                get_app_page(nxt.page_key),
                label=f"下一阶段：{nxt.title} →",
                icon=nxt.icon,
            )
