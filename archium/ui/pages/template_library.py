"""Template library — unified entry for template studio and induction."""

from __future__ import annotations

import streamlit as st

from archium.ui.pages import template_induction, template_studio


def render() -> None:
    st.markdown("### 模板库")
    st.caption("管理参考模板与模板归纳结果。日常制作请走「制作」五阶段。")
    studio_tab, induction_tab = st.tabs(["模板工作室", "模板归纳"])
    with studio_tab:
        template_studio.render()
    with induction_tab:
        template_induction.render()
