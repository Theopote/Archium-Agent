"""Unified AI modification workspace — edit input + proposal review in one flow."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.config.settings import Settings
from archium.domain.visual.edit_intent import INTENT_USER_LABELS, VisualEditIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.studio.proposal_compare_panel import (
    get_stored_proposal,
    render_proposal_compare_panel,
    store_proposal,
)
from archium.ui.studio_service import (
    apply_slide_visual_edit,
    create_slide_scene_proposal_from_text,
    restore_slide_visual_edit,
)
from archium.ui.visual_service import SlideVisualSnapshot


def render_ai_workspace(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
    presentation_id: UUID,
    settings: Settings,
) -> None:
    """Single AI Tab workspace: request → proposal → before/after → accept."""
    st.markdown("**修改建议 · AI 修改 · 需确认**")
    if slide_snapshot is None:
        st.caption("请选择页面后再编辑。")
        return

    slide_id = slide_snapshot.slide.id
    if slide_snapshot.render_scene is None:
        st.caption("当前页尚无 RenderScene，暂仅支持版式直接编辑。")
        _render_legacy_panel(slide_id=slide_id)
        return

    st.caption(
        "修改范围默认：当前页面。"
        "保护：锁定内容、素材身份、页面事实与引用保持不变。"
    )
    text = st.text_area(
        "输入修改要求",
        placeholder="例如：标题改为「结论：…」、放大总平面图、修复文字溢出…",
        height=100,
        key=f"studio_ai_edit_input_{slide_id}",
    )
    scope = st.radio(
        "修改范围",
        options=["当前页面", "选中对象", "指定区域"],
        horizontal=True,
        key=f"studio_ai_edit_scope_{slide_id}",
        disabled=True,
        help="当前版本以整页提案为主；选中对象 / 指定区域将在后续开放。",
    )
    _ = scope

    if st.button(
        "生成修改提案",
        type="primary",
        use_container_width=True,
        key=f"studio_create_proposal_{slide_id}",
    ):
        _run_proposal(slide_id=slide_id, text=text.strip())

    proposal = get_stored_proposal(slide_id)
    if proposal is None:
        st.caption("生成提案后，将在此显示修改前 / 修改后对比与接受操作。")
    else:
        st.divider()
        render_proposal_compare_panel(
            slide_snapshot=slide_snapshot,
            presentation_id=presentation_id,
            settings=settings,
            embedded=True,
        )

    with st.expander("版式直接编辑（不经提案确认）", expanded=False):
        st.caption("安全提示：直接写入版式，无 Before/After。优先使用上方提案流程。")
        _render_legacy_panel(slide_id=slide_id)


def _render_legacy_panel(*, slide_id: UUID) -> None:
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
        [VisualEditIntent.FIX_OVERFLOW, VisualEditIntent.BALANCE_COLUMNS],
    ]
    for row in preset_rows:
        cols = st.columns(len(row))
        for column, intent in zip(cols, row, strict=True):
            with column:
                if st.button(
                    INTENT_USER_LABELS[intent],
                    use_container_width=True,
                    key=f"studio_intent_{intent.value}_{slide_id}",
                ):
                    _run_edit(slide_id=slide_id, text=INTENT_USER_LABELS[intent])

    if st.button("撤销上一步", use_container_width=True, key=f"studio_undo_edit_{slide_id}"):
        try:
            with st.spinner("正在撤销…"), get_session() as session:
                restore_slide_visual_edit(session, slide_id)
            st.success("已撤销一步视觉修改。")
            st.rerun()
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        except Exception as exc:
            st.error(format_user_error(exc))


def _run_proposal(*, slide_id: UUID, text: str) -> None:
    if not text:
        st.error("请先描述想做的修改。")
        return
    try:
        with st.spinner("正在生成修改提案…"), get_session() as session:
            proposal = create_slide_scene_proposal_from_text(session, slide_id, text)
        store_proposal(proposal)
        st.success("修改提案已生成，请在下方对比后接受或拒绝。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _run_edit(*, slide_id: UUID, text: str) -> None:
    if not text:
        st.error("请先描述想做的修改。")
        return
    try:
        with st.spinner("正在应用修改…"), get_session() as session:
            apply_slide_visual_edit(session, slide_id, text)
        st.success("已应用视觉修改。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
