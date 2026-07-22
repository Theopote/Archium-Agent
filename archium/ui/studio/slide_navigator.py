"""Slide list navigation for Presentation Studio — status-aware page rail."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from archium.domain.page_pipeline_status import PagePipelineStatus
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.layout_family_ui import format_layout_family_label
from archium.ui.page_status_board_panel import (
    load_page_status_board,
    render_compact_page_actions,
    status_badge,
    status_short_detail,
)
from archium.ui.studio_service import (
    StudioPresentationContext,
    add_studio_slide,
    delete_studio_slide,
    get_selected_slide_snapshot,
    reorder_studio_slide,
)


def _set_selected_slide(index: int) -> None:
    st.session_state.studio_selected_slide_index = index


def _move_slide(context: StudioPresentationContext, from_index: int, to_index: int) -> None:
    try:
        with get_session() as session:
            reorder_studio_slide(
                session,
                context.presentation.id,
                from_index=from_index,
                to_index=to_index,
            )
        st.session_state.studio_selected_slide_index = to_index
        st.success(f"已将 P{from_index + 1} 移动到 P{to_index + 1}。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _status_by_slide(context: StudioPresentationContext) -> dict[str, PagePipelineStatus]:
    try:
        board = load_page_status_board(context.presentation.id)
    except Exception:
        return {}
    mapping: dict[str, PagePipelineStatus] = {}
    for row in board.rows:
        if row.slide_id is not None:
            mapping[str(row.slide_id)] = row
    return mapping


def render_slide_navigator(*, context: StudioPresentationContext) -> int:
    """Render status-aware page list and return the selected slide index."""
    st.markdown("**页面**")
    slides = context.snapshot.slides
    if not slides:
        st.caption("当前汇报还没有页面。")
        return 0

    selected_index = int(st.session_state.get("studio_selected_slide_index", 0))
    focus_slide_id = st.session_state.pop("studio_focus_slide_id", None)
    if focus_slide_id:
        for index, item in enumerate(slides):
            if str(item.slide.id) == str(focus_slide_id):
                selected_index = index
                break
    selected_index = max(0, min(selected_index, len(slides) - 1))
    status_map = _status_by_slide(context)

    manage_cols = st.columns(2)
    with manage_cols[0]:
        if st.button(
            "新增",
            key=f"studio_add_slide_{context.presentation.id}",
            use_container_width=True,
        ):
            try:
                with get_session() as session:
                    new_slide = add_studio_slide(
                        session,
                        context.presentation.id,
                        after_index=selected_index,
                    )
                st.session_state.studio_selected_slide_index = selected_index + 1
                st.success(f"已新增 P{new_slide.order + 1}。")
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))
    with manage_cols[1]:
        current = slides[selected_index]
        if st.button(
            "删除",
            key=f"studio_delete_slide_{context.presentation.id}",
            use_container_width=True,
            disabled=len(slides) <= 1,
        ):
            try:
                with get_session() as session:
                    delete_studio_slide(session, current.slide.id)
                st.session_state.studio_selected_slide_index = max(0, selected_index - 1)
                st.success("已删除当前页。")
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))

    with st.expander("排序", expanded=False):
        reorder_cols = st.columns([1, 1, 2])
        with reorder_cols[0]:
            if st.button(
                "上移",
                key=f"studio_move_up_{context.presentation.id}",
                use_container_width=True,
                disabled=selected_index <= 0,
            ):
                _move_slide(context, selected_index, selected_index - 1)
        with reorder_cols[1]:
            if st.button(
                "下移",
                key=f"studio_move_down_{context.presentation.id}",
                use_container_width=True,
                disabled=selected_index >= len(slides) - 1,
            ):
                _move_slide(context, selected_index, selected_index + 1)
        with reorder_cols[2]:
            target_options = list(range(len(slides)))
            move_to = st.selectbox(
                "移到位置",
                options=target_options,
                index=selected_index,
                format_func=lambda value: f"P{value + 1}",
                key=f"studio_move_to_{context.presentation.id}",
                label_visibility="collapsed",
            )
            if move_to != selected_index and st.button(
                "确认移动",
                key=f"studio_move_confirm_{context.presentation.id}",
                use_container_width=True,
            ):
                _move_slide(context, selected_index, move_to)

    for index, item in enumerate(slides):
        slide = item.slide
        row = status_map.get(str(slide.id))
        badge = status_badge(row) if row is not None else "○"
        order_label = f"{slide.order + 1:02d}"
        title = (slide.title or "未命名")[:16]
        hint = ""
        if row is not None and row.severity in {"warn", "error", "info"}:
            detail = status_short_detail(row)
            if detail and badge != "✓":
                hint = f"  {detail}"
        is_selected = index == selected_index
        label = f"{order_label}  {title}  {badge}{hint}"

        with st.container(border=is_selected):
            preview_path = item.preview_image
            if is_selected and preview_path and Path(preview_path).is_file():
                st.image(preview_path, use_container_width=True)

            if st.button(
                label,
                key=f"studio_nav_slide_{context.presentation.id}_{index}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                _set_selected_slide(index)
                st.rerun()

            if is_selected and row is not None:
                render_compact_page_actions(
                    presentation_id=context.presentation.id,
                    project_id=context.project.id,
                    row=row,
                    key_prefix=f"studio_nav_actions_{context.presentation.id}",
                )

    st.session_state.studio_selected_slide_index = selected_index
    current_snapshot = get_selected_slide_snapshot(context, selected_index)
    if current_snapshot is not None:
        plan = current_snapshot.layout_plan
        family = format_layout_family_label(plan.layout_family) if plan else "待生成版式"
        st.caption(f"当前：P{current_snapshot.slide.order + 1} · {family}")
    return selected_index
