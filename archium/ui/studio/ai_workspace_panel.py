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
    create_slide_scene_proposal_from_element_comment,
    create_slide_scene_proposal_from_text,
    resolve_selected_render_node_id,
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

    selected_ids = list(st.session_state.get("studio_selected_element_ids") or [])
    if not selected_ids:
        raw = st.session_state.get("studio_selected_element_id")
        if isinstance(raw, str) and raw:
            selected_ids = [raw]

    bound_nodes: list[tuple[str, str | None]] = []
    for element_id in selected_ids:
        node_id, layout_id = resolve_selected_render_node_id(slide_snapshot, element_id)
        if node_id:
            bound_nodes.append((node_id, layout_id))

    st.caption(
        "保护：锁定内容、素材身份、页面事实与引用保持不变。"
        "评论会绑定当前 Scene Revision / hash / node_snapshot。"
    )
    text = st.text_area(
        "输入修改要求",
        placeholder="例如：标题改为「结论：…」、放大总平面图、修复文字溢出…",
        height=100,
        key=f"studio_ai_edit_input_{slide_id}",
    )
    scope = st.radio(
        "修改范围",
        options=["选中对象", "多选", "选区(包围盒)", "当前页面"],
        horizontal=True,
        key=f"studio_ai_edit_scope_{slide_id}",
        help="选区=多选节点的包围盒 region 评论；多选=SELECTION scope。",
    )
    if bound_nodes:
        labels = ", ".join(f"`{nid}`" for nid, _ in bound_nodes[:6])
        st.caption(f"当前选中节点：{labels}" + ("…" if len(bound_nodes) > 6 else ""))
    else:
        st.caption("未选中元素时，「选中对象 / 多选」不可用；请用「当前页面」。")

    if st.button(
        "生成修改提案",
        type="primary",
        use_container_width=True,
        key=f"studio_create_proposal_{slide_id}",
    ):
        _run_scoped_proposal(
            slide_id=slide_id,
            text=text.strip(),
            scope_label=scope,
            bound_nodes=bound_nodes,
            slide_snapshot=slide_snapshot,
        )

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


def _run_scoped_proposal(
    *,
    slide_id: UUID,
    text: str,
    scope_label: str,
    bound_nodes: list[tuple[str, str | None]],
    slide_snapshot: SlideVisualSnapshot | None = None,
) -> None:
    if not text:
        st.error("请先描述想做的修改。")
        return
    try:
        with st.spinner("正在生成修改提案…"), get_session() as session:
            if scope_label == "当前页面" or not bound_nodes:
                proposal = create_slide_scene_proposal_from_text(session, slide_id, text)
            elif scope_label == "选区(包围盒)" and len(bound_nodes) >= 1:
                from archium.application.visual.comment_region import selection_region_bbox

                primary_id, layout_id = bound_nodes[0]
                node_ids = [nid for nid, _ in bound_nodes]
                extras = node_ids[1:]
                region = None
                if slide_snapshot is not None and slide_snapshot.render_scene is not None:
                    region = selection_region_bbox(slide_snapshot.render_scene, node_ids)
                proposal = create_slide_scene_proposal_from_element_comment(
                    session,
                    slide_id,
                    node_id=primary_id,
                    note=text,
                    layout_element_id=layout_id,
                    scope="region",
                    scope_node_ids=extras,
                    region_bbox=region,
                )
            elif scope_label == "多选" and len(bound_nodes) >= 2:
                primary_id, layout_id = bound_nodes[0]
                extras = [nid for nid, _ in bound_nodes[1:]]
                proposal = create_slide_scene_proposal_from_element_comment(
                    session,
                    slide_id,
                    node_id=primary_id,
                    note=text,
                    layout_element_id=layout_id,
                    scope="selection",
                    scope_node_ids=extras,
                )
            else:
                primary_id, layout_id = bound_nodes[0]
                proposal = create_slide_scene_proposal_from_element_comment(
                    session,
                    slide_id,
                    node_id=primary_id,
                    note=text,
                    layout_element_id=layout_id,
                    scope="node",
                )
        store_proposal(proposal)
        st.success("修改提案已生成，请在下方对比后接受或拒绝。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


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


def _run_edit(*, slide_id: UUID, text: str) -> None:
    if not text:
        st.error("请先描述想做的修改。")
        return
    try:
        with st.spinner("正在应用…"), get_session() as session:
            apply_slide_visual_edit(session, slide_id, text=text)
        st.success("已直接应用视觉修改。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
