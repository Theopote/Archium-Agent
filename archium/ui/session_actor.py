"""Streamlit session actor identity (Topic 08 C1 / COLLAB-003)."""

from __future__ import annotations

from archium.domain.access import LOCAL_ACTOR_ID

_SESSION_KEY = "actor_id"


def get_current_actor_id() -> str:
    """Return session actor_id; default ``local-user`` for single-seat mode."""
    try:
        import streamlit as st

        raw = st.session_state.get(_SESSION_KEY)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()[:200]
        st.session_state[_SESSION_KEY] = LOCAL_ACTOR_ID
        return LOCAL_ACTOR_ID
    except Exception:
        return LOCAL_ACTOR_ID


def set_current_actor_id(actor_id: str) -> str:
    """Set session actor (invite redeem / dev switch). Returns normalized id."""
    normalized = (actor_id or "").strip()[:200] or LOCAL_ACTOR_ID
    try:
        import streamlit as st

        st.session_state[_SESSION_KEY] = normalized
    except Exception:
        pass
    return normalized
