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
    create_slide_scene_proposal_from_element_comment,
    create_slide_scene_proposal_from_intent,
    create_slide_scene_proposal_from_text,
    resolve_selected_render_node_id,
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

    selected_raw = st.session_state.get("studio_selected_element_id")
    selected_element_id = selected_raw if isinstance(selected_raw, str) else None
    bound_node_id, layout_element_id = resolve_selected_render_node_id(
        slide_snapshot,
        selected_element_id,
    )

    st.caption(
        "Scene 提案模式：自然语言 → StudioCommand → Before/After → 接受后写入 Revision。"
        "系统规则：**只修改我提到的部分**"
        "（未指定节点 / 锁定节点 / 素材身份 / 页面事实 / 引用保持不变）。"
        "选中元素后评论可硬绑定目标节点，无需描述「右边第二张图」。"
    )

    if bound_node_id:
        label = layout_element_id or bound_node_id
        st.info(f"当前目标：`{bound_node_id}`" + (f"（layout `{label}`）" if label != bound_node_id else ""))
    else:
        st.caption("未选中元素：将按纯自然语言解析目标（可能需要描述位置/角色）。")

    text = st.text_area(
        "描述你想做的修改",
        placeholder="例如：放大一点并和左边对齐；或标题改为「结论：…」、修复文字溢出…",
        height=100,
        key=f"studio_ai_edit_input_{slide_id}",
    )

    button_label = "对选中元素生成提案" if bound_node_id else "生成修改提案"
    if st.button(
        button_label,
        type="primary",
        use_container_width=True,
        key=f"studio_create_proposal_{slide_id}",
    ):
        if bound_node_id:
            _run_element_comment_proposal(
                slide_id=slide_id,
                node_id=bound_node_id,
                layout_element_id=layout_element_id,
                text=text.strip(),
            )
        else:
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


def _run_element_comment_proposal(
    *,
    slide_id: UUID,
    node_id: str,
    layout_element_id: str | None,
    text: str,
) -> None:
    if not text:
        st.error("请输入修改描述。")
        return
    try:
        with st.spinner("正在按选中元素生成 Before/After 提案…"), get_session() as session:
            proposal = create_slide_scene_proposal_from_element_comment(
                session,
                slide_id,
                node_id=node_id,
                note=text,
                layout_element_id=layout_element_id,
            )
        store_proposal(proposal)
        st.success("元素评论提案已生成，请在下方 Scene 修改提案面板查看对比。")
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
