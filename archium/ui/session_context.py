"""Single source of truth for project/presentation UI selection state."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any
from uuid import UUID


def _id(value: UUID | str) -> str:
    return str(value)


def select_project_context(
    state: MutableMapping[str, Any],
    project_id: UUID | str,
    *,
    presentation_id: UUID | str | None = None,
) -> bool:
    """Select a project and clear state that belongs to the previous project."""
    selected = _id(project_id)
    changed = str(state.get("selected_project_id") or "") != selected
    state["selected_project_id"] = selected
    if not changed:
        if presentation_id is not None:
            select_presentation_context(state, presentation_id)
        return False

    state["selected_presentation_id"] = (
        _id(presentation_id) if presentation_id is not None else None
    )
    state["studio_selected_slide_index"] = 0
    state["studio_selected_element_id"] = None
    state["studio_selected_element_ids"] = []
    state["last_visual_workflow_result"] = None
    state["last_presentation_critique"] = None
    return True


def select_presentation_context(
    state: MutableMapping[str, Any],
    presentation_id: UUID | str,
) -> bool:
    """Select a presentation and reset slide/element state when it changes."""
    selected = _id(presentation_id)
    changed = str(state.get("selected_presentation_id") or "") != selected
    state["selected_presentation_id"] = selected
    if changed:
        state["studio_selected_slide_index"] = 0
        state["studio_selected_element_id"] = None
        state["studio_selected_element_ids"] = []
        state["last_visual_workflow_result"] = None
        state["last_presentation_critique"] = None
    return changed
