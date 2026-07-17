"""
Archium（阿基姆）— Streamlit Web 前端
"""

from __future__ import annotations

import streamlit as st

from archium.ui.bootstrap import (
    inject_styles,
    init_app,
    render_branding,
    render_discord_settings,
    render_module_status,
)
from archium.ui.pages import command_center, home, workspace

st.set_page_config(
    page_title="Archium · 阿基姆",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_app()
inject_styles()

with st.sidebar:
    render_branding()
    render_module_status()
    render_discord_settings()
    st.markdown(
        '<div style="margin-top:2rem;font-size:0.72rem;color:#bbb9b2;line-height:1.6;">'
        "Archium v0.2<br>建筑 · 归档 · 智能"
        "</div>",
        unsafe_allow_html=True,
    )

navigation = st.navigation(
    [
        st.Page(home.render, title="首页", icon="🏛️", default=True),
        st.Page(workspace.render, title="项目工作台", icon="📁"),
        st.Page(command_center.render, title="指令中心", icon="💬"),
    ]
)
navigation.run()
