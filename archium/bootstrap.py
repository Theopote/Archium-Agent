"""Unified application startup.

All formal entry points (``archium`` CLI, ``app.py``, smoke launchers) must go
through this module so environment loading, settings, logging, database init,
and the Streamlit shell stay consistent regardless of process cwd.
"""

from __future__ import annotations

from pathlib import Path

from archium.config.settings import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


def load_environment() -> Path:
    """Load ``.env`` from the repository root (not the process cwd)."""
    from dotenv import load_dotenv

    load_dotenv(ENV_PATH)
    return ENV_PATH


def bootstrap_runtime(*, settings: Settings | None = None) -> Settings:
    """Initialize env, logging, settings directories, and the database.

    Safe to call outside Streamlit (tests, scripts). Idempotent enough for
    repeated calls: settings are cached; ``init_database`` is additive.
    """
    load_environment()
    from archium.config.settings import get_settings
    from archium.infrastructure.database.session import init_database
    from archium.logging import setup_logging

    resolved = settings or get_settings()
    setup_logging(resolved)
    init_database()
    return resolved


def create_application() -> None:
    """Build and run the Streamlit product UI.

    This is the single Streamlit shell: page config, runtime bootstrap, styles,
    page registration, sidebar chrome, and session cleanup.
    """
    import streamlit as st

    from archium.infrastructure.database.session import close_scoped_session
    from archium.ui.app_navigation import build_app_pages
    from archium.ui.bootstrap import inject_styles, render_branding
    from archium.ui.branding import render_version_footer
    from archium.ui.project_progress_card import render_project_progress_card

    st.set_page_config(
        page_title="Archium · 阿基姆",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Drop any leftover scoped session from a previous script rerun, then boot once.
    close_scoped_session()
    if not st.session_state.get("_archium_initialized"):
        bootstrap_runtime()
        st.session_state._archium_initialized = True

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
        close_scoped_session()
