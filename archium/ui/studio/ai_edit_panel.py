"""AI natural-language edit panel for Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.domain.visual.edit_intent import INTENT_USER_LABELS, VisualEditIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.studio_service import (
    apply_slide_visual_edit,
    restore_slide_visual_edit,
)
from archium.ui.visual_service import SlideVisualSnapshot


def render_ai_edit_panel(*, slide_snapshot: SlideVisualSnapshot | None) -> None:
    """Render NL edit controls wired to visual edit + revision services."""
    st.markdown("**AI 编辑**")
    if slide_snapshot is None:
        st.caption("请选择页面后再编辑。")
        return

    slide_id = slide_snapshot.slide.id
    st.caption("支持 8 种高频修改：版式、留白、主图、锁定与撤销。")

    text = st.text_area(
        "描述你想做的修改",
        placeholder="例如：减少文字、放大主图、切换到图纸版式…",
        height=100,
        key=f"studio_ai_edit_input_{slide_id}",
    )

    if st.button("应用修改", type="primary", use_container_width=True, key=f"studio_apply_edit_{slide_id}"):
        _run_edit(slide_id=slide_id, text=text.strip())

    preset_rows = [
        [
            VisualEditIntent.REDUCE_TEXT,
            VisualEditIntent.ENLARGE_HERO,
        ],
        [
            VisualEditIntent.INCREASE_WHITESPACE,
            VisualEditIntent.CHANGE_LAYOUT,
        ],
        [
            VisualEditIntent.SET_HERO_ASSET,
            VisualEditIntent.REMOVE_ASSET,
        ],
        [
            VisualEditIntent.LOCK_ELEMENT,
            VisualEditIntent.RESTORE_PREVIOUS,
        ],
    ]
    for row in preset_rows:
        cols = st.columns(2)
        for column, intent in zip(cols, row, strict=True):
            label = INTENT_USER_LABELS[intent]
            if column.button(
                label,
                use_container_width=True,
                key=f"studio_preset_{intent.value}_{slide_id}",
            ):
                if intent == VisualEditIntent.RESTORE_PREVIOUS:
                    _run_restore(slide_id=slide_id)
                else:
                    _run_edit(slide_id=slide_id, intent=intent.value)


def _run_edit(*, slide_id: UUID, text: str = "", intent: str | None = None) -> None:
    try:
        with st.spinner("正在应用修改并重新校验版式…"), get_session() as session:
            if text:
                result = apply_slide_visual_edit(session, slide_id, text=text)
            else:
                result = apply_slide_visual_edit(session, slide_id, intent=intent)
        message = getattr(result, "message", None) or "修改已应用。"
        st.success(message)
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _run_restore(*, slide_id: UUID) -> None:
    try:
        with st.spinner("正在恢复上一版视觉状态…"), get_session() as session:
            result = restore_slide_visual_edit(session, slide_id)
        message = getattr(result, "message", None) or "已恢复上一版。"
        st.success(message)
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
