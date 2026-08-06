"""Single source of truth for project/presentation UI selection state."""

from __future__ import annotations

from typing import Any
from uuid import UUID

# Streamlit selectbox ``key`` values that mirror SSOT selection.
_PROJECT_WIDGET_KEYS = (
    "studio_compact_project",
    "studio_project_select",
    "deliver_switch_project",
)
_PRESENTATION_WIDGET_KEYS = (
    "studio_compact_presentation",
    "studio_presentation_select",
    "deliver_switch_presentation",
)
_ALIGNED_PROJECT_KEY = "_aligned_project_id"
_ALIGNED_PRESENTATION_KEY = "_aligned_presentation_id"


def _id(value: UUID | str) -> str:
    return str(value)


def _sync_widget_keys(state: Any, keys: tuple[str, ...], selected: str) -> None:
    for key in keys:
        if state.get(key) != selected:
            state[key] = selected


def reconcile_project_widgets(state: Any, valid_ids: list[str]) -> str | None:
    """Keep project selectbox keys in sync with SSOT without clobbering user input.

    Streamlit writes the widget key *before* the script reruns. Blindly copying
    ``selected_project_id`` onto the widget key therefore undoes the user's pick.
    We only push SSOT → widgets when SSOT changed externally (home / deliver /
    another page) since the last reconcile.
    """
    if not valid_ids:
        return None
    ssot = str(state.get("selected_project_id") or "")
    if ssot not in valid_ids:
        ssot = valid_ids[0]
        state["selected_project_id"] = ssot
    last = str(state.get(_ALIGNED_PROJECT_KEY) or "")
    if ssot != last:
        _sync_widget_keys(state, _PROJECT_WIDGET_KEYS, ssot)
        state[_ALIGNED_PROJECT_KEY] = ssot
    else:
        # Ensure widgets exist / stay valid without overriding a same-SSOT pick.
        for key in _PROJECT_WIDGET_KEYS:
            if state.get(key) not in valid_ids:
                state[key] = ssot
    return ssot


def reconcile_presentation_widgets(state: Any, valid_ids: list[str]) -> str | None:
    """Same reconcile rules for presentation selectboxes."""
    if not valid_ids:
        return None
    ssot = str(state.get("selected_presentation_id") or "")
    if ssot not in valid_ids:
        ssot = valid_ids[0]
        state["selected_presentation_id"] = ssot
    last = str(state.get(_ALIGNED_PRESENTATION_KEY) or "")
    if ssot != last:
        _sync_widget_keys(state, _PRESENTATION_WIDGET_KEYS, ssot)
        state[_ALIGNED_PRESENTATION_KEY] = ssot
    else:
        for key in _PRESENTATION_WIDGET_KEYS:
            if state.get(key) not in valid_ids:
                state[key] = ssot
    return ssot


def select_project_context(
    state: Any,
    project_id: UUID | str,
    *,
    presentation_id: UUID | str | None = None,
) -> bool:
    """Select a project and clear state that belongs to the previous project."""
    selected = _id(project_id)
    changed = str(state.get("selected_project_id") or "") != selected
    state["selected_project_id"] = selected
    _sync_widget_keys(state, _PROJECT_WIDGET_KEYS, selected)
    state[_ALIGNED_PROJECT_KEY] = selected
    if not changed:
        if presentation_id is not None:
            select_presentation_context(state, presentation_id)
        return False

    state["selected_presentation_id"] = (
        _id(presentation_id) if presentation_id is not None else None
    )
    for key in _PRESENTATION_WIDGET_KEYS:
        state.pop(key, None)
    state.pop(_ALIGNED_PRESENTATION_KEY, None)
    if presentation_id is not None:
        select_presentation_context(state, presentation_id)
    state["studio_selected_slide_index"] = 0
    state["studio_selected_element_id"] = None
    state["studio_selected_element_ids"] = []
    state["last_visual_workflow_result"] = None
    state["last_presentation_critique"] = None
    return True


def select_presentation_context(
    state: Any,
    presentation_id: UUID | str,
) -> bool:
    """Select a presentation and reset slide/element state when it changes."""
    selected = _id(presentation_id)
    changed = str(state.get("selected_presentation_id") or "") != selected
    state["selected_presentation_id"] = selected
    _sync_widget_keys(state, _PRESENTATION_WIDGET_KEYS, selected)
    state[_ALIGNED_PRESENTATION_KEY] = selected
    if changed:
        state["studio_selected_slide_index"] = 0
        state["studio_selected_element_id"] = None
        state["studio_selected_element_ids"] = []
        state["last_visual_workflow_result"] = None
        state["last_presentation_critique"] = None
    return changed
