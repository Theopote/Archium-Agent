"""Invite deep-link helpers (Topic 08 C2 / COLLAB-004)."""

from __future__ import annotations

import contextlib

import streamlit as st

_PENDING_KEY = "pending_invite_code"


def consume_invite_query_param() -> str | None:
    """Read ``?invite=CODE`` into session and clear the query param."""
    code = ""
    try:
        raw = st.query_params.get("invite")
        if isinstance(raw, list):
            raw = raw[0] if raw else ""
        code = str(raw or "").strip().upper()
    except Exception:
        return peek_pending_invite_code()
    if not code:
        return peek_pending_invite_code()
    st.session_state[_PENDING_KEY] = code[:40]
    with contextlib.suppress(Exception):
        del st.query_params["invite"]
    return code[:40]


def peek_pending_invite_code() -> str | None:
    raw = st.session_state.get(_PENDING_KEY)
    if isinstance(raw, str) and raw.strip():
        return raw.strip().upper()[:40]
    return None


def clear_pending_invite_code() -> None:
    st.session_state.pop(_PENDING_KEY, None)


def invite_share_path(code: str) -> str:
    """Relative share hint for Streamlit query (open Home to redeem)."""
    return f"?invite={str(code).strip().upper()}"
