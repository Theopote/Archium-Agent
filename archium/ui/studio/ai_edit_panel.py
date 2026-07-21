"""AI natural-language edit panel for Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.domain.visual.edit_intent import INTENT_USER_LABELS, VisualEditIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.studio.proposal_compare_panel import store_proposal
from archium.ui.studio_service import (
    apply_slide_visual_edit,
    create_slide_scene_proposal_from_intent,
    create_slide_scene_proposal_from_text,
    restore_slide_visual_edit,
)
from archium.ui.visual_service import SlideVisualSnapshot


def render_ai_edit_panel(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
    presentation_id: UUID | None = None,
) -> None:
    """Render NL edit controls that produce SceneChangeProposal workflows."""
    st.markdown("**AI 编辑**")
    if slide_snapshot is None:
        st.caption("请选择页面后再编辑。")
        return

    slide_id = slide_snapshot.slide.id
    if slide_snapshot.render_scene is None:
        st.caption("当前页尚无 RenderScene，暂仅支持版式直接编辑。")
        _render_legacy_panel(slide_id=slide_id)
        return

    st.caption(
        "Scene 提案模式：自然语言会先解析为结构化命令，再生成 Before/After 对比。"
        "支持：改写标题/正文、修复文字溢出、减少文字。"
    )

    text = st.text_area(
        "描述你想做的修改",
        placeholder="例如：标题改为「结论：院区交通需分层组织」、修复文字溢出、减少文字…",
        height=100,
        key=f"studio_ai_edit_input_{slide_id}",
    )

    if st.button(
        "生成修改提案",
        type="primary",
        use_container_width=True,
        key=f"studio_create_proposal_{slide_id}",
    ):
        _run_proposal(slide_id=slide_id, text=text.strip())

    with st.expander("版式直接编辑（不经 Scene 提案）", expanded=False):
        _render_legacy_panel(slide_id=slide_id)


def _render_legacy_panel(*, slide_id: UUID) -> None:
    st.caption("以下操作直接修改 LayoutPlan，不经过 Scene 提案对比。")

    if st.button(
        "直接应用上方描述",
        use_container_width=True,
        key=f"studio_apply_edit_{slide_id}",
    ):
        text = str(st.session_state.get(f"studio_ai_edit_input_{slide_id}", "")).strip()
        _run_edit(slide_id=slide_id, text=text)

    preset_rows = [
        [VisualEditIntent.REDUCE_TEXT, VisualEditIntent.ENLARGE_HERO],
        [VisualEditIntent.INCREASE_WHITESPACE, VisualEditIntent.CHANGE_LAYOUT],
        [VisualEditIntent.SET_HERO_ASSET, VisualEditIntent.REMOVE_ASSET],
        [VisualEditIntent.LOCK_ELEMENT, VisualEditIntent.UNLOCK_ELEMENT],
        [VisualEditIntent.RESTORE_PREVIOUS],
    ]
    for row in preset_rows:
        cols = st.columns(len(row))
        for column, intent in zip(cols, row, strict=True):
            label = INTENT_USER_LABELS[intent]
            if column.button(
                label,
                use_container_width=True,
                key=f"studio_preset_{intent.value}_{slide_id}",
            ):
                if intent == VisualEditIntent.RESTORE_PREVIOUS:
                    _run_restore(slide_id=slide_id)
                elif intent == VisualEditIntent.REDUCE_TEXT:
                    _run_proposal_from_intent(slide_id=slide_id, intent=intent)
                else:
                    _run_edit(slide_id=slide_id, intent=intent.value)


def _run_proposal(*, slide_id: UUID, text: str) -> None:
    if not text:
        st.error("请输入修改描述。")
        return
    try:
        with st.spinner("正在解析指令并生成 Before/After 提案…"), get_session() as session:
            proposal = create_slide_scene_proposal_from_text(session, slide_id, text)
        store_proposal(proposal)
        st.success("修改提案已生成，请在下方 Scene 修改提案面板查看对比。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _run_proposal_from_intent(*, slide_id: UUID, intent: VisualEditIntent) -> None:
    try:
        with st.spinner("正在生成 Scene 修改提案…"), get_session() as session:
            proposal = create_slide_scene_proposal_from_intent(session, slide_id, intent)
        store_proposal(proposal)
        st.success("修改提案已生成。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


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
