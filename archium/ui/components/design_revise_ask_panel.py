"""Ask/Apply panel for pending Critic→Revise offers (Phase L2 + Topic 07 durable)."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import streamlit as st

from archium.application.unit_of_work import unit_of_work
from archium.ui.components.design_reflection_details import render_design_reflection


def hydrate_pending_revise_from_db(project_id: UUID | None) -> None:
    """Load durable Ask into session when session is empty (Topic 07 / APP-026)."""
    if project_id is None:
        return
    existing = st.session_state.get("pending_design_revise")
    if isinstance(existing, dict) and existing.get("direction_id"):
        return
    try:
        from archium.application.design_revise_persistence import (
            load_pending_design_revise,
        )
        from archium.application.unit_of_work import unit_of_work

        with unit_of_work() as uow:
            pending = load_pending_design_revise(uow, project_id)
        if pending:
            st.session_state["pending_design_revise"] = pending
            critique = pending.get("critique")
            if isinstance(critique, dict):
                st.session_state["last_design_critique_report"] = critique
    except Exception:
        return


def clear_pending_revise_state(project_id: UUID | None = None) -> None:
    """Clear session + durable Ask."""
    st.session_state.pop("pending_design_revise", None)
    if project_id is None:
        raw = st.session_state.get("selected_project_id")
        try:
            project_id = UUID(str(raw)) if raw else None
        except (TypeError, ValueError):
            project_id = None
    if project_id is None:
        return
    try:
        from archium.application.design_revise_persistence import (
            clear_pending_design_revise,
        )

        with unit_of_work() as uow:
            clear_pending_design_revise(uow, project_id)
    except Exception:
        return


def render_pending_revise_ask(
    *,
    key_prefix: str,
    on_apply: Callable[[UUID], None],
    on_reject: Callable[[UUID], None],
    on_dismiss: Callable[[], None] | None = None,
    project_id: UUID | None = None,
) -> None:
    """Render Apply/Reject UI from session (hydrated from DB when needed)."""
    hydrate_pending_revise_from_db(project_id)
    pending = st.session_state.get("pending_design_revise")
    if not isinstance(pending, dict) or not pending.get("direction_id"):
        return

    try:
        direction_id = UUID(str(pending["direction_id"]))
    except (TypeError, ValueError):
        clear_pending_revise_state(project_id)
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
                # Keep durable pending; only leave the panel for now
                st.rerun()


def store_pending_revise_from_selection(selection: object) -> bool:
    """If selection awaits Ask, stash offer in session + Project. Return True when pending."""
    if getattr(selection, "selection_completed", True):
        project_id = None
        direction = getattr(selection, "direction", None)
        if direction is not None:
            project_id = getattr(direction, "project_id", None)
        mission = getattr(selection, "mission", None)
        if project_id is None and mission is not None:
            project_id = getattr(mission, "project_id", None)
        if project_id is None:
            pending = st.session_state.get("pending_design_revise")
            if isinstance(pending, dict) and pending.get("project_id"):
                try:
                    project_id = UUID(str(pending["project_id"]))
                except (TypeError, ValueError):
                    project_id = None
        clear_pending_revise_state(
            UUID(str(project_id)) if project_id is not None else None
        )
        return False
    pending = getattr(selection, "pending_revise", None)
    if pending is None:
        return False
    if hasattr(pending, "as_dict"):
        payload = pending.as_dict()
    elif isinstance(pending, dict):
        payload = pending
    else:
        return False
    st.session_state["pending_design_revise"] = payload
    report = getattr(selection, "critique_report", None)
    if report is not None and hasattr(report, "as_dict"):
        st.session_state["last_design_critique_report"] = report.as_dict()
    warnings = list(getattr(selection, "critique_warnings", None) or [])
    if warnings:
        st.session_state["design_critique_warnings"] = warnings

    try:
        project_id = UUID(str(payload.get("project_id")))
    except (TypeError, ValueError):
        return True
    try:
        from archium.application.design_revise_persistence import (
            persist_pending_design_revise,
        )

        with unit_of_work() as uow:
            persist_pending_design_revise(uow, project_id, payload)
    except Exception:
        from archium.logging import get_logger

        get_logger(__name__).debug(
            'persist pending design revise failed',
            exc_info=True,
        )
    return True
