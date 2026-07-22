"""Archium（阿基姆）— Streamlit Web 前端."""

from __future__ import annotations

import streamlit as st

from archium.ui.app_navigation import build_app_pages
from archium.ui.bootstrap import (
    init_app,
    inject_styles,
    render_branding,
    render_version_footer,
)
from archium.ui.project_progress_card import render_project_progress_card

st.set_page_config(
    page_title="Archium · 阿基姆",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_app()
inject_styles()

try:
    # Register pages before sidebar chrome so st.page_link resolves.
    pages = build_app_pages()
    with st.sidebar:
        render_branding()
        render_project_progress_card()
        render_version_footer()

    navigation = st.navigation(pages)
    navigation.run()
finally:
    from archium.infrastructure.database.session import close_scoped_session

    close_scoped_session()
