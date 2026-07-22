"""Undo/redo toolbar for Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.studio.undo_stack import content_redo_depth, visual_redo_depth
from archium.ui.studio_service import (
    count_content_undo_steps,
    count_visual_undo_steps,
    redo_slide_content_adaptation,
    redo_slide_visual_edit,
    undo_slide_content_adaptation,
    undo_slide_visual_edit,
)
from archium.ui.visual_service import SlideVisualSnapshot


def render_undo_toolbar(*, slide_snapshot: SlideVisualSnapshot | None) -> None:
    """Render visual/content undo and redo controls above the canvas."""
    if slide_snapshot is None:
        return

    slide_id = slide_snapshot.slide.id
    with get_session() as session:
        visual_undo_steps = count_visual_undo_steps(session, slide_id)
        content_undo_steps = count_content_undo_steps(session, slide_id)
    visual_redo_steps = visual_redo_depth(slide_id)
    content_redo_steps = content_redo_depth(slide_id)

    st.caption("画布拖拽、移动与缩放会写入 Scene 修订；可用撤销/重做回退。")

    cols = st.columns(4)
    with cols[0]:
        if st.button(
            f"撤销视觉 ({visual_undo_steps})",
            use_container_width=True,
            disabled=visual_undo_steps == 0,
            key=f"studio_undo_visual_{slide_id}",
        ):
            _run_visual_undo(slide_id=slide_id)
    with cols[1]:
        if st.button(
            f"重做视觉 ({visual_redo_steps})",
            use_container_width=True,
            disabled=visual_redo_steps == 0,
            key=f"studio_redo_visual_{slide_id}",
        ):
            _run_visual_redo(slide_id=slide_id)
    with cols[2]:
        if st.button(
            f"撤销内容 ({content_undo_steps})",
            use_container_width=True,
            disabled=content_undo_steps == 0,
            key=f"studio_undo_content_{slide_id}",
        ):
            _run_content_undo(slide_id=slide_id)
    with cols[3]:
        if st.button(
            f"重做内容 ({content_redo_steps})",
            use_container_width=True,
            disabled=content_redo_steps == 0,
            key=f"studio_redo_content_{slide_id}",
        ):
            _run_content_redo(slide_id=slide_id)

    st.caption("画布支持拖拽移动与右下角缩放；撤销/重做基于版本历史，可连续多步操作。")


def _run_visual_undo(*, slide_id: UUID) -> None:
    try:
        with st.spinner("正在撤销视觉修改…"), get_session() as session:
            result = undo_slide_visual_edit(session, slide_id)
        st.success(_visual_history_message(result, fallback="已撤销一步视觉修改。"))
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _run_visual_redo(*, slide_id: UUID) -> None:
    try:
        with st.spinner("正在重做视觉修改…"), get_session() as session:
            result = redo_slide_visual_edit(session, slide_id)
        st.success(_visual_history_message(result, fallback="已重做一步视觉修改。"))
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _visual_history_message(result: object, *, fallback: str) -> str:
    summary = getattr(result, "summary", None)
    if summary is not None and hasattr(summary, "summary"):
        text = str(summary.summary).strip()
        if text:
            return text
    message = getattr(result, "message", None)
    if message:
        return str(message)
    return fallback


def _run_content_undo(*, slide_id: UUID) -> None:
    try:
        with st.spinner("正在撤销内容修改…"), get_session() as session:
            undo_slide_content_adaptation(session, slide_id)
        st.success("已撤销一步内容修改。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _run_content_redo(*, slide_id: UUID) -> None:
    try:
        with st.spinner("正在重做内容修改…"), get_session() as session:
            redo_slide_content_adaptation(session, slide_id)
        st.success("已重做一步内容修改。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
