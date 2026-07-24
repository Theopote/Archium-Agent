"""Streamlit helpers for resolving effective LLM settings."""

from __future__ import annotations

import streamlit as st

from archium.application.llm_settings_resolver import get_effective_settings
from archium.config.settings import Settings


def session_api_key() -> str | None:
    value = st.session_state.get("llm_session_api_key")
    return value if isinstance(value, str) and value else None


def get_ui_effective_settings() -> Settings:
    """Resolve LLM settings using the current Streamlit session state."""
    return get_effective_settings(session_api_key=session_api_key())
