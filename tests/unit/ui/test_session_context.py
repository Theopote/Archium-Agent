"""Selection-state reset contracts for cross-page project context."""

from __future__ import annotations

from archium.ui.session_context import (
    select_presentation_context,
    select_project_context,
)


def _state() -> dict[str, object]:
    return {
        "selected_project_id": "project-a",
        "selected_presentation_id": "deck-a",
        "studio_selected_slide_index": 7,
        "studio_selected_element_id": "node-a",
        "studio_selected_element_ids": ["node-a", "node-b"],
        "last_visual_workflow_result": object(),
        "last_presentation_critique": {"score": 3},
        "studio_advanced_mode": True,
    }


def test_project_switch_clears_project_bound_state() -> None:
    state = _state()
    assert select_project_context(state, "project-b")
    assert state["selected_project_id"] == "project-b"
    assert state["selected_presentation_id"] is None
    assert state["studio_selected_slide_index"] == 0
    assert state["studio_selected_element_id"] is None
    assert state["studio_selected_element_ids"] == []
    assert state["last_visual_workflow_result"] is None
    assert state["last_presentation_critique"] is None
    assert state["studio_advanced_mode"] is True


def test_same_project_preserves_current_presentation() -> None:
    state = _state()
    assert not select_project_context(state, "project-a")
    assert state["selected_presentation_id"] == "deck-a"
    assert state["studio_selected_slide_index"] == 7


def test_project_switch_can_select_matching_presentation_atomically() -> None:
    state = _state()
    assert select_project_context(state, "project-b", presentation_id="deck-b")
    assert state["selected_project_id"] == "project-b"
    assert state["selected_presentation_id"] == "deck-b"


def test_presentation_switch_resets_slide_and_selection() -> None:
    state = _state()
    assert select_presentation_context(state, "deck-b")
    assert state["selected_presentation_id"] == "deck-b"
    assert state["studio_selected_slide_index"] == 0
    assert state["studio_selected_element_ids"] == []


def test_same_presentation_is_noop() -> None:
    state = _state()
    assert not select_presentation_context(state, "deck-a")
    assert state["studio_selected_slide_index"] == 7
