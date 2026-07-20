"""Session-scoped redo stacks for Studio undo/redo."""

from __future__ import annotations

from uuid import UUID

import streamlit as st


def _visual_redo_key(slide_id: UUID) -> str:
    return f"studio_visual_redo_stack_{slide_id}"


def _content_redo_key(slide_id: UUID) -> str:
    return f"studio_content_redo_stack_{slide_id}"


def clear_visual_redo_stack(slide_id: UUID) -> None:
    st.session_state[_visual_redo_key(slide_id)] = []


def push_visual_redo_revision(slide_id: UUID, revision_id: UUID) -> None:
    stack = list(st.session_state.get(_visual_redo_key(slide_id), []))
    stack.append(str(revision_id))
    st.session_state[_visual_redo_key(slide_id)] = stack


def pop_visual_redo_revision(slide_id: UUID) -> UUID | None:
    stack = list(st.session_state.get(_visual_redo_key(slide_id), []))
    if not stack:
        return None
    revision_id = UUID(stack.pop())
    st.session_state[_visual_redo_key(slide_id)] = stack
    return revision_id


def visual_redo_depth(slide_id: UUID) -> int:
    return len(st.session_state.get(_visual_redo_key(slide_id), []))


def clear_content_redo_stack(slide_id: UUID) -> None:
    st.session_state[_content_redo_key(slide_id)] = []


def push_content_redo_revision(slide_id: UUID, revision_id: UUID) -> None:
    stack = list(st.session_state.get(_content_redo_key(slide_id), []))
    stack.append(str(revision_id))
    st.session_state[_content_redo_key(slide_id)] = stack


def pop_content_redo_revision(slide_id: UUID) -> UUID | None:
    stack = list(st.session_state.get(_content_redo_key(slide_id), []))
    if not stack:
        return None
    revision_id = UUID(stack.pop())
    st.session_state[_content_redo_key(slide_id)] = stack
    return revision_id


def content_redo_depth(slide_id: UUID) -> int:
    return len(st.session_state.get(_content_redo_key(slide_id), []))
