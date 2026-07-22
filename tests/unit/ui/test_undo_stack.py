"""Session redo-stack helpers for Studio undo/redo."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.ui.studio.undo_stack import (
    clear_all_visual_redo_stacks,
    clear_visual_redo_stack,
    pop_visual_redo_revision,
    push_visual_redo_revision,
    visual_redo_depth,
)


def test_clear_visual_redo_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    import streamlit as st

    state: dict[str, object] = {}

    class _SessionState(dict):
        def get(self, key, default=None):  # type: ignore[no-untyped-def]
            return super().get(key, default)

    monkeypatch.setattr(st, "session_state", _SessionState(state))
    slide_id = uuid4()
    push_visual_redo_revision(slide_id, uuid4())
    assert visual_redo_depth(slide_id) == 1
    clear_visual_redo_stack(slide_id)
    assert visual_redo_depth(slide_id) == 0
    assert pop_visual_redo_revision(slide_id) is None


def test_clear_all_visual_redo_stacks(monkeypatch: pytest.MonkeyPatch) -> None:
    import streamlit as st

    state: dict[str, object] = {}

    class _SessionState(dict):
        def get(self, key, default=None):  # type: ignore[no-untyped-def]
            return super().get(key, default)

        def keys(self):  # type: ignore[no-untyped-def]
            return super().keys()

    monkeypatch.setattr(st, "session_state", _SessionState(state))
    a = uuid4()
    b = uuid4()
    push_visual_redo_revision(a, uuid4())
    push_visual_redo_revision(b, uuid4())
    clear_all_visual_redo_stacks()
    assert visual_redo_depth(a) == 0
    assert visual_redo_depth(b) == 0
