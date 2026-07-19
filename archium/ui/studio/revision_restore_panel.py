"""Revision restore controls for Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.slide_diff import change_source_label
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.studio_service import (
    list_slide_content_revisions,
    list_slide_visual_revisions,
    restore_slide_content_at_revision,
    restore_slide_visual_at_revision,
)
from archium.ui.visual_service import SlideVisualSnapshot


def _revision_label(revision: object) -> str:
    note = getattr(revision, "note", None) or ""
    number = getattr(revision, "revision_number", "?")
    source = change_source_label(revision.change_source)
    created = getattr(revision, "created_at", None)
    time_label = created.strftime("%m-%d %H:%M") if created is not None else "—"
    return f"#{number} · {source} · {note or '修订'} · {time_label}"


def render_visual_revision_panel(*, slide_snapshot: SlideVisualSnapshot | None) -> None:
    if slide_snapshot is None:
        return
    slide_id = slide_snapshot.slide.id
    with get_session() as session:
        revisions = list_slide_visual_revisions(session, slide_id)
    if not revisions:
        return
    with st.expander("视觉修订历史", expanded=False):
        st.caption("选择任意视觉版本恢复（会先保存当前状态）。")
        for revision in revisions[:8]:
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(_revision_label(revision))
            with cols[1]:
                if st.button(
                    "恢复",
                    key=f"studio_restore_visual_{slide_id}_{revision.id}",
                    use_container_width=True,
                ):
                    _restore_visual(slide_id=slide_id, revision_id=revision.id)


def render_content_revision_panel(*, slide_snapshot: SlideVisualSnapshot | None) -> None:
    if slide_snapshot is None:
        return
    slide_id = slide_snapshot.slide.id
    with get_session() as session:
        revisions = list_slide_content_revisions(session, slide_id)
    if not revisions:
        return
    with st.expander("内容适配修订", expanded=False):
        st.caption("恢复到任意内容适配前的版本。")
        for revision in revisions[:8]:
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(_revision_label(revision))
            with cols[1]:
                if st.button(
                    "恢复",
                    key=f"studio_restore_content_{slide_id}_{revision.id}",
                    use_container_width=True,
                ):
                    _restore_content(slide_id=slide_id, revision_id=revision.id)


def _restore_visual(*, slide_id: UUID, revision_id: UUID) -> None:
    try:
        with st.spinner("正在恢复视觉版本…"), get_session() as session:
            restore_slide_visual_at_revision(session, slide_id, revision_id)
        st.success("已恢复到所选视觉版本。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _restore_content(*, slide_id: UUID, revision_id: UUID) -> None:
    try:
        with st.spinner("正在恢复内容版本…"), get_session() as session:
            restore_slide_content_at_revision(session, slide_id, revision_id)
        st.success("已恢复到所选内容版本。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
