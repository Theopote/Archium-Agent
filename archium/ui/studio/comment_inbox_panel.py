"""Comment Inbox — presentation-wide element comment triage for Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.domain.visual.element_comment import ElementComment, ElementCommentStatus
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.visual_service import SlideVisualSnapshot

_STATUS_LABELS = {
    "pending": "待处理",
    "proposed": "已生成提案",
    "needs_rebase": "待确认(需 rebase)",
    "accepted": "已接受",
    "rejected": "已拒绝",
    "resolved": "已解决",
}


def render_comment_inbox(
    *,
    presentation_id: UUID,
    slide_snapshot: SlideVisualSnapshot | None = None,
) -> None:
    """Unified comment inbox with status counts and filters."""
    st.markdown("**评论 Inbox**")
    current_slide_id = slide_snapshot.slide.id if slide_snapshot is not None else None

    try:
        with get_session() as session:
            from archium.application.visual.element_comment_service import (
                ElementCommentService,
            )

            service = ElementCommentService(session)
            counts = service.inbox_counts(presentation_id)
            comments = service.list_for_presentation(presentation_id)
    except Exception as exc:
        st.error(format_user_error(exc))
        return

    cols = st.columns(6)
    metrics = [
        ("pending", "待处理"),
        ("proposed", "已生成提案"),
        ("needs_rebase", "待确认"),
        ("resolved", "已解决"),
        ("accepted", "已接受"),
        ("rejected", "无法解析/拒绝"),
    ]
    for column, (key, label) in zip(cols, metrics, strict=True):
        column.metric(label, counts.get(key, 0))

    filter_cols = st.columns(4)
    with filter_cols[0]:
        scope_page = st.selectbox(
            "页面",
            options=["全部页面", "仅当前页"],
            key=f"studio_comment_inbox_page_{presentation_id}",
            disabled=current_slide_id is None,
        )
    with filter_cols[1]:
        status_filter = st.multiselect(
            "状态",
            options=list(_STATUS_LABELS.keys()),
            default=["pending", "proposed", "needs_rebase"],
            format_func=lambda value: _STATUS_LABELS.get(value, value),
            key=f"studio_comment_inbox_status_{presentation_id}",
        )
    with filter_cols[2]:
        sort_by = st.selectbox(
            "排序",
            options=["创建时间↓", "创建时间↑", "状态"],
            key=f"studio_comment_inbox_sort_{presentation_id}",
        )
    with filter_cols[3]:
        author_filter = st.text_input(
            "创建人",
            value="",
            placeholder="可选",
            key=f"studio_comment_inbox_author_{presentation_id}",
        )

    filtered = list(comments)
    if scope_page == "仅当前页" and current_slide_id is not None:
        filtered = [item for item in filtered if item.slide_id == current_slide_id]
    if status_filter:
        filtered = [item for item in filtered if item.status.value in status_filter]
    if author_filter.strip():
        needle = author_filter.strip().lower()
        filtered = [item for item in filtered if needle in (item.created_by or "").lower()]

    if sort_by == "创建时间↑":
        filtered.sort(key=lambda item: item.created_at)
    elif sort_by == "状态":
        filtered.sort(key=lambda item: (item.status.value, item.created_at), reverse=True)
    else:
        filtered.sort(key=lambda item: item.created_at, reverse=True)

    if not filtered:
        st.caption("没有匹配的评论。")
        return

    for comment in filtered[:40]:
        _render_comment_row(comment, presentation_id=presentation_id)


def _render_comment_row(comment: ElementComment, *, presentation_id: UUID) -> None:
    status = _STATUS_LABELS.get(comment.status.value, comment.status.value)
    scope_bits = [comment.scope.value]
    if comment.scope_node_ids:
        scope_bits.append(f"+{len(comment.scope_node_ids)} nodes")
    if comment.region_bbox:
        scope_bits.append("region")
    header = (
        f"`{comment.node_id}` · {status} · "
        f"{' · '.join(scope_bits)} · {comment.created_by}"
    )
    with st.expander(header, expanded=False):
        st.write(comment.note)
        st.caption(
            f"slide `{comment.slide_id}` · revision "
            f"`{comment.scene_revision_id}` · hash `{comment.scene_hash[:12] if comment.scene_hash else '—'}`"
        )
        if comment.status == ElementCommentStatus.NEEDS_REBASE:
            if st.button(
                "重新绑定到当前 Scene",
                key=f"studio_comment_rebind_{comment.id}",
                use_container_width=True,
            ):
                _rebind(comment.id)
        if comment.status in {
            ElementCommentStatus.PENDING,
            ElementCommentStatus.PROPOSED,
            ElementCommentStatus.NEEDS_REBASE,
        }:
            if st.button(
                "标记已解决",
                key=f"studio_comment_resolve_{comment.id}",
                use_container_width=True,
            ):
                _resolve(comment.id)


def _rebind(comment_id: UUID) -> None:
    try:
        with get_session() as session:
            from archium.application.visual.element_comment_service import (
                ElementCommentService,
            )

            ElementCommentService(session).rebind_to_current_scene(comment_id)
        st.success("已重新绑定到当前 Scene。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _resolve(comment_id: UUID) -> None:
    try:
        with get_session() as session:
            from archium.application.visual.element_comment_service import (
                ElementCommentService,
            )

            ElementCommentService(session).resolve_comment(comment_id)
        st.success("评论已标记为已解决。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
