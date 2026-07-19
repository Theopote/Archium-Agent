"""
Archium（阿基姆）— Streamlit Web 前端
"""

from __future__ import annotations

import streamlit as st
from archium.ui.app_navigation import build_app_pages
from archium.ui.bootstrap import (
    init_app,
    inject_styles,
    render_branding,
    render_module_status,
)

st.set_page_config(
    page_title="Archium · 阿基姆",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_app()
inject_styles()

try:
    with st.sidebar:
        render_branding()
        render_module_status()
        st.markdown(
            '<div style="margin-top:2rem;font-size:0.72rem;color:#bbb9b2;line-height:1.6;">'
            "Archium v0.2-alpha.5<br>建筑 · 归档 · 智能"
            "</div>",
            unsafe_allow_html=True,
        )

    navigation = st.navigation(build_app_pages())
    navigation.run()
finally:
    from archium.infrastructure.database.session import close_scoped_session

    close_scoped_session()
