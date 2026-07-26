"""Ask/Apply panel for pending Critic→Revise offers (Phase L2)."""

from __future__ import annotations

from typing import Callable
from uuid import UUID

import streamlit as st

from archium.ui.components.design_reflection_details import render_design_reflection


def render_pending_revise_ask(
    *,
    key_prefix: str,
    on_apply: Callable[[UUID], None],
    on_reject: Callable[[UUID], None],
    on_dismiss: Callable[[], None] | None = None,
) -> None:
    """Render Apply/Reject UI from ``st.session_state['pending_design_revise']``."""
    pending = st.session_state.get("pending_design_revise")
    if not isinstance(pending, dict) or not pending.get("direction_id"):
        return

    try:
        direction_id = UUID(str(pending["direction_id"]))
    except (TypeError, ValueError):
        st.session_state.pop("pending_design_revise", None)
        return

    st.warning("设计批判建议修订该方向。请确认是否应用补丁后再选定。")
    diff_lines = pending.get("diff_lines") or []
    if isinstance(diff_lines, list) and diff_lines:
        st.markdown("**修订预览**")
        for line in diff_lines[:10]:
            st.markdown(f"- {line}")

    reflection = pending.get("reflection")
    if reflection:
        render_design_reflection(
            reflection,
            expanded=True,
            title="可执行调整（Apply 将写入方向）",
        )

    cols = st.columns(3)
    with cols[0]:
        if st.button(
            "应用修订并选定",
            key=f"{key_prefix}_revise_apply",
            type="primary",
            use_container_width=True,
        ):
            on_apply(direction_id)
    with cols[1]:
        if st.button(
            "拒绝修订，按原方向选定",
            key=f"{key_prefix}_revise_reject",
            use_container_width=True,
        ):
            on_reject(direction_id)
    with cols[2]:
        if st.button(
            "稍后决定",
            key=f"{key_prefix}_revise_dismiss",
            use_container_width=True,
        ):
            if on_dismiss is not None:
                on_dismiss()
            else:
                st.session_state.pop("pending_design_revise", None)
                st.rerun()


def store_pending_revise_from_selection(selection: object) -> bool:
    """If selection awaits Ask, stash offer in session state. Return True when pending."""
    if getattr(selection, "selection_completed", True):
        st.session_state.pop("pending_design_revise", None)
        return False
    pending = getattr(selection, "pending_revise", None)
    if pending is None:
        return False
    if hasattr(pending, "as_dict"):
        st.session_state["pending_design_revise"] = pending.as_dict()
    elif isinstance(pending, dict):
        st.session_state["pending_design_revise"] = pending
    else:
        return False
    report = getattr(selection, "critique_report", None)
    if report is not None and hasattr(report, "as_dict"):
        st.session_state["last_design_critique_report"] = report.as_dict()
    warnings = list(getattr(selection, "critique_warnings", None) or [])
    if warnings:
        st.session_state["design_critique_warnings"] = warnings
    return True
