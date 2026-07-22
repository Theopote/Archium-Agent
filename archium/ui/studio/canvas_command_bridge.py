"""Bridge canvas pointer-up events to Studio geometry commands."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.visual.element_geometry import (
    layout_bounds_from_percent,
    layout_coords_from_percent,
)
from archium.domain.visual.layout import LayoutPlan
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error


def canvas_component_key(slide_id: UUID) -> str:
    """Streamlit component key; bump generation after geometry commits to reset widget state."""
    generation = int(st.session_state.get(_generation_key(slide_id), 0))
    return f"canvas_{slide_id}_{generation}"


def bump_canvas_generation(slide_id: UUID) -> None:
    st.session_state[_generation_key(slide_id)] = (
        int(st.session_state.get(_generation_key(slide_id), 0)) + 1
    )


def set_studio_selection(element_ids: list[str]) -> None:
    """Persist multi-select; singular key stays primary (first) for panels."""
    cleaned = [item for item in element_ids if item]
    st.session_state.studio_selected_element_ids = cleaned
    st.session_state.studio_selected_element_id = cleaned[0] if cleaned else None


def geometry_event_fingerprint(
    event_kind: str,
    element_id: str,
    *values: float,
) -> str:
    rounded = ",".join(f"{value:.4f}" for value in values)
    return f"{event_kind}:{element_id}:{rounded}"


def apply_canvas_move_event(
    *,
    slide_id: UUID,
    plan: LayoutPlan,
    element_id: str,
    x_percent: float,
    y_percent: float,
) -> bool:
    """Persist a canvas drag as MoveNodeCommand. Returns True when a command was applied."""
    fingerprint = geometry_event_fingerprint("move", element_id, x_percent, y_percent)
    if _already_applied(slide_id, fingerprint):
        return False

    x, y = layout_coords_from_percent(plan, x_percent=x_percent, y_percent=y_percent)
    try:
        from archium.ui.studio_service import apply_slide_element_move

        with get_session() as session:
            apply_slide_element_move(
                session,
                slide_id,
                element_id=element_id,
                x=x,
                y=y,
            )
    except WorkflowError as exc:
        st.error(format_user_error(exc))
        return False
    except Exception as exc:
        st.error(format_user_error(exc))
        return False

    _mark_applied(slide_id, fingerprint)
    set_studio_selection([element_id])
    bump_canvas_generation(slide_id)
    st.rerun()
    return True


def apply_canvas_move_many_event(
    *,
    slide_id: UUID,
    plan: LayoutPlan,
    moves: list[tuple[str, float, float]],
) -> bool:
    """Persist multi-select drag as one MoveNodesCommand (one revision)."""
    if not moves:
        return False
    fingerprint_parts: list[str] = []
    resolved: list[tuple[str, float, float]] = []
    for element_id, x_percent, y_percent in moves:
        fingerprint_parts.append(
            geometry_event_fingerprint("moveMany", element_id, x_percent, y_percent)
        )
        x, y = layout_coords_from_percent(plan, x_percent=x_percent, y_percent=y_percent)
        resolved.append((element_id, x, y))
    fingerprint = "|".join(sorted(fingerprint_parts))
    if _already_applied(slide_id, fingerprint):
        return False

    try:
        from archium.ui.studio_service import apply_slide_element_moves

        with get_session() as session:
            apply_slide_element_moves(session, slide_id, moves=resolved)
    except WorkflowError as exc:
        st.error(format_user_error(exc))
        return False
    except Exception as exc:
        st.error(format_user_error(exc))
        return False

    _mark_applied(slide_id, fingerprint)
    set_studio_selection([element_id for element_id, _x, _y in resolved])
    bump_canvas_generation(slide_id)
    st.rerun()
    return True


def apply_canvas_resize_event(
    *,
    slide_id: UUID,
    plan: LayoutPlan,
    element_id: str,
    x_percent: float,
    y_percent: float,
    width_percent: float,
    height_percent: float,
    preserve_aspect_ratio: bool = False,
) -> bool:
    """Persist a canvas resize as ResizeNodeCommand. Returns True when a command was applied."""
    fingerprint = geometry_event_fingerprint(
        "resize",
        element_id,
        x_percent,
        y_percent,
        width_percent,
        height_percent,
    )
    if _already_applied(slide_id, fingerprint):
        return False

    x, y, width, height = layout_bounds_from_percent(
        plan,
        x_percent=x_percent,
        y_percent=y_percent,
        width_percent=width_percent,
        height_percent=height_percent,
    )
    try:
        from archium.ui.studio_service import apply_slide_element_resize

        with get_session() as session:
            apply_slide_element_resize(
                session,
                slide_id,
                element_id=element_id,
                x=x,
                y=y,
                width=width,
                height=height,
                preserve_aspect_ratio=preserve_aspect_ratio,
            )
    except WorkflowError as exc:
        st.error(format_user_error(exc))
        return False
    except Exception as exc:
        st.error(format_user_error(exc))
        return False

    _mark_applied(slide_id, fingerprint)
    set_studio_selection([element_id])
    bump_canvas_generation(slide_id)
    st.rerun()
    return True


def apply_canvas_commit_text_event(
    *,
    slide_id: UUID,
    element_id: str,
    text: str,
) -> bool:
    """Persist inline canvas text edit (one RewriteText / visual edit revision)."""
    fingerprint = f"commitText:{element_id}:{hash(text)}"
    if _already_applied(slide_id, fingerprint):
        return False
    try:
        from archium.ui.studio_service import apply_slide_element_text

        with get_session() as session:
            apply_slide_element_text(
                session,
                slide_id,
                element_id=element_id,
                text=text,
            )
    except WorkflowError as exc:
        st.error(format_user_error(exc))
        return False
    except Exception as exc:
        st.error(format_user_error(exc))
        return False

    _mark_applied(slide_id, fingerprint)
    set_studio_selection([element_id])
    bump_canvas_generation(slide_id)
    st.rerun()
    return True


def apply_canvas_commit_replace_asset_event(
    *,
    slide_id: UUID,
    element_id: str,
    asset_id: str,
) -> bool:
    """Persist canvas image replace via set_element_asset intent."""
    fingerprint = f"commitReplaceAsset:{element_id}:{asset_id}"
    if _already_applied(slide_id, fingerprint):
        return False
    try:
        from archium.ui.studio_service import apply_slide_visual_edit
        from archium.ui.studio.undo_stack import clear_visual_redo_stack

        clear_visual_redo_stack(slide_id)
        with get_session() as session:
            apply_slide_visual_edit(
                session,
                slide_id,
                intent="set_element_asset",
                params={"element_id": element_id, "content_ref": asset_id},
            )
    except WorkflowError as exc:
        st.error(format_user_error(exc))
        return False
    except Exception as exc:
        st.error(format_user_error(exc))
        return False

    _mark_applied(slide_id, fingerprint)
    set_studio_selection([element_id])
    bump_canvas_generation(slide_id)
    st.rerun()
    return True


def _generation_key(slide_id: UUID) -> str:
    return f"studio_canvas_gen_{slide_id}"


def _applied_key(slide_id: UUID) -> str:
    return f"studio_canvas_applied_{slide_id}"


def _already_applied(slide_id: UUID, fingerprint: str) -> bool:
    return st.session_state.get(_applied_key(slide_id)) == fingerprint


def _mark_applied(slide_id: UUID, fingerprint: str) -> None:
    st.session_state[_applied_key(slide_id)] = fingerprint
