"""Content adaptation controls for Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.domain.content_adaptation import (
    ACTION_USER_LABELS,
    ContentAdaptationAction,
    parse_content_adaptation_text,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.studio_service import apply_slide_content_adaptation
from archium.ui.visual_service import SlideVisualSnapshot


def render_content_adaptation_panel(*, slide_snapshot: SlideVisualSnapshot | None) -> None:
    """Render SlideSpec content adaptation actions."""
    st.markdown("**内容适配**")
    if slide_snapshot is None:
        st.caption("请选择页面后再调整内容。")
        return

    slide_id = slide_snapshot.slide.id
    st.caption("调整页面文字与结构；修改后会尝试重新生成版式并记录修订。")

    text = st.text_area(
        "描述内容调整",
        placeholder="例如：缩短文字、转为要点、拆分页面、突出核心信息…",
        height=80,
        key=f"studio_content_adapt_input_{slide_id}",
    )

    if st.button(
        "应用内容适配",
        use_container_width=True,
        key=f"studio_apply_content_adapt_{slide_id}",
    ):
        action = parse_content_adaptation_text(text.strip())
        if action is None:
            st.error("无法识别内容适配意图。请使用下方按钮或更明确的描述。")
        else:
            _run_adaptation(slide_id=slide_id, action=action.value)

    actions = [
        ContentAdaptationAction.SHORTEN,
        ContentAdaptationAction.CONVERT_TO_BULLETS,
        ContentAdaptationAction.SPLIT_SLIDE,
        ContentAdaptationAction.PROMOTE_KEY_MESSAGE,
    ]
    cols = st.columns(2)
    for index, action in enumerate(actions):
        column = cols[index % 2]
        if column.button(
            ACTION_USER_LABELS[action],
            use_container_width=True,
            key=f"studio_content_{action.value}_{slide_id}",
        ):
            _run_adaptation(slide_id=slide_id, action=action.value)


def _run_adaptation(*, slide_id: UUID, action: str) -> None:
    try:
        with st.spinner("正在适配页面内容并更新版式…"), get_session() as session:
            result = apply_slide_content_adaptation(session, slide_id, action=action)
        message = getattr(result, "message", None) or "内容适配已完成。"
        st.success(message)
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
