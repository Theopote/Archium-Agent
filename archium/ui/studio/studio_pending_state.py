"""Pending session-state updates for Studio chrome widgets.

Prefer logical flags (``studio_show_inspector``) over widget keys
(``studio_ui_show_inspector``). When a caller must change UI before the next
render, stash values here; ``apply_pending_studio_chrome()`` copies them at
the top of ``studio.render()``.
"""

from __future__ import annotations

from uuid import UUID

import streamlit as st

PENDING_SHOW_INSPECTOR = "_studio_pending_show_inspector"
PENDING_SHOW_NAV = "_studio_pending_show_nav"
PENDING_INSPECTOR_TAB = "_studio_pending_inspector_tab"
PENDING_INSPECTOR_EXPANDED = "_studio_pending_inspector_expanded"
PENDING_CENTER_MODE = "_studio_pending_center_mode"


def ai_edit_pending_key(slide_id: UUID) -> str:
    return f"studio_ai_edit_pending_{slide_id}"


def apply_pending_studio_chrome() -> None:
    """Apply deferred chrome toggles before Studio widgets are created."""
    if PENDING_SHOW_INSPECTOR in st.session_state:
        st.session_state.studio_show_inspector = bool(
            st.session_state.pop(PENDING_SHOW_INSPECTOR)
        )
    if PENDING_SHOW_NAV in st.session_state:
        st.session_state.studio_show_nav = bool(st.session_state.pop(PENDING_SHOW_NAV))
    if PENDING_INSPECTOR_TAB in st.session_state:
        st.session_state.studio_inspector_tab = st.session_state.pop(PENDING_INSPECTOR_TAB)
    if PENDING_INSPECTOR_EXPANDED in st.session_state:
        st.session_state.studio_inspector_expanded = bool(
            st.session_state.pop(PENDING_INSPECTOR_EXPANDED)
        )
    if PENDING_CENTER_MODE in st.session_state:
        st.session_state.studio_center_mode = st.session_state.pop(PENDING_CENTER_MODE)


def open_modify_with_prompt(slide_id: UUID, prompt: str) -> None:
    """Open the modify inspector and pre-fill the AI edit prompt."""
    request_open_modify(slide_id=slide_id, prompt=prompt)


def request_open_modify(*, slide_id: UUID | None = None, prompt: str | None = None) -> None:
    """Open the modify inspector. Safe: logical keys are not widget-bound."""
    st.session_state[PENDING_SHOW_INSPECTOR] = True
    st.session_state[PENDING_INSPECTOR_EXPANDED] = True
    st.session_state[PENDING_INSPECTOR_TAB] = "修改"
    if slide_id is not None and prompt is not None and str(prompt).strip():
        st.session_state[ai_edit_pending_key(slide_id)] = str(prompt).strip()


def request_show_inspector(*, show: bool) -> None:
    st.session_state[PENDING_SHOW_INSPECTOR] = bool(show)


def request_show_nav(*, show: bool) -> None:
    st.session_state[PENDING_SHOW_NAV] = bool(show)


def request_center_mode(mode: str) -> None:
    st.session_state[PENDING_CENTER_MODE] = mode
