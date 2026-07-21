"""Per-page pipeline status board — real page lines + recovery actions."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.page_status_board_service import (
    PageStatusBoardService,
    action_label,
)
from archium.domain.page_pipeline_status import PageStatusAction
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.label_map import entity_label

_SEVERITY_ICON = {
    "success": "✅",
    "info": "⏳",
    "warn": "⚠️",
    "error": "❌",
}


def render_page_status_board(
    *,
    presentation_id: UUID,
    project_id: UUID | None = None,
    workflow_run_id: UUID | None = None,
    workflow_step: str | None = None,
    compact: bool = False,
    key_prefix: str = "page_status",
    title: str | None = None,
) -> None:
    """Render per-page status lines and action buttons."""
    with get_session() as session:
        board = PageStatusBoardService(session).build_board(
            presentation_id,
            workflow_step=workflow_step,
        )

    if not board.rows:
        if not compact:
            st.caption("生成页面后将在此显示逐页真实状态。")
        return

    heading = title if title is not None else ("逐页状态" if not compact else "")
    if heading:
        st.markdown(f"#### {heading}")
    if not compact:
        st.caption(board.summary or "每页真实进度（不只是「正在生成…」）")
    elif board.summary:
        st.caption(board.summary)

    for row in board.rows:
        icon = _SEVERITY_ICON.get(row.severity, "•")
        title_bit = f" · {row.title}" if row.title and not compact else ""
        line = f"{icon} {row.display_line()}{title_bit}"
        if row.detail and not compact:
            line = f"{line}  \n  {row.detail}"
        elif row.detail and compact:
            line = f"{line} — {row.detail}"

        if compact:
            st.markdown(line)
            continue

        with st.container(border=True):
            st.markdown(line)
            if not row.actions or row.slide_id is None:
                continue
            cols = st.columns(min(len(row.actions), 5))
            for column, action in zip(cols, row.actions, strict=False):
                button_key = f"{key_prefix}_{presentation_id}_{row.slide_id}_{action.value}"
                if column.button(
                    action_label(action),
                    key=button_key,
                    use_container_width=True,
                ):
                    _handle_action(
                        presentation_id=presentation_id,
                        project_id=project_id,
                        slide_id=row.slide_id,
                        action=action,
                        workflow_run_id=workflow_run_id,
                    )


def _handle_action(
    *,
    presentation_id: UUID,
    project_id: UUID | None,
    slide_id: UUID,
    action: PageStatusAction,
    workflow_run_id: UUID | None,
) -> None:
    if action == PageStatusAction.OPEN_STUDIO:
        _open_studio(presentation_id, project_id=project_id, slide_id=slide_id)
        return
    if action == PageStatusAction.CHANGE_TEMPLATE:
        _open_studio(
            presentation_id,
            project_id=project_id,
            slide_id=slide_id,
            toast="已打开 Studio，请在「版式候选」中更换模板。",
        )
        return
    if action == PageStatusAction.REBIND_ASSETS:
        st.session_state["review_focus_asset_board"] = True
        st.session_state["review_focus_slide_id"] = str(slide_id)
        try:
            with get_session() as session:
                PageStatusBoardService(session).run_action(
                    presentation_id,
                    slide_id,
                    PageStatusAction.REBIND_ASSETS,
                    workflow_run_id=workflow_run_id,
                )
            st.success("已重新匹配该页素材。可在素材看板确认。")
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        st.rerun()
        return

    try:
        with get_session() as session:
            PageStatusBoardService(session).run_action(
                presentation_id,
                slide_id,
                action,
                workflow_run_id=workflow_run_id,
            )
        if action == PageStatusAction.RETRY:
            st.success(f"已重试该页{entity_label('SlideSpec')}。")
        elif action == PageStatusAction.SKIP:
            st.info("已跳过该页（不阻塞整套交付）。")
        elif action == PageStatusAction.UNSKIP:
            st.success("已取消跳过。")
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    st.rerun()


def _open_studio(
    presentation_id: UUID,
    *,
    project_id: UUID | None,
    slide_id: UUID,
    toast: str | None = None,
) -> None:
    st.session_state["selected_presentation_id"] = str(presentation_id)
    if project_id is not None:
        st.session_state["selected_project_id"] = str(project_id)
    st.session_state["studio_focus_slide_id"] = str(slide_id)
    st.session_state["review_focus_slide_id"] = str(slide_id)
    message = toast or "正在打开汇报工作室…"
    st.toast(message)
    try:
        from archium.ui.app_navigation import get_app_page

        st.switch_page(get_app_page("studio"))
    except Exception:
        st.info("请切换到「汇报工作室」继续编辑该页。")
