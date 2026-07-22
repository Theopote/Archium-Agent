"""Per-page pipeline status board — real page lines + recovery actions."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.page_status_board_service import (
    PageStatusBoardService,
    action_label,
)
from archium.domain.page_pipeline_status import (
    PAGE_PHASE_LABELS,
    PagePipelinePhase,
    PagePipelineStatus,
    PageStatusAction,
    PageStatusBoard,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.label_map import entity_label

_SEVERITY_META: dict[str, dict[str, str]] = {
    "success": {"mark": "✓", "label": "完成", "css": "ok"},
    "info": {"mark": "…", "label": "进行中", "css": "info"},
    "warn": {"mark": "!", "label": "需注意", "css": "warn"},
    "error": {"mark": "✕", "label": "失败", "css": "error"},
}


def _severity_meta(severity: str) -> dict[str, str]:
    return _SEVERITY_META.get(
        severity, {"mark": "○", "label": "未知", "css": "neutral"}
    )


def status_label(row: PagePipelineStatus) -> str:
    """Human-readable status label (not emoji-only)."""
    if row.phase == PagePipelinePhase.COMPLETE or row.severity == "success":
        return "完成"
    if row.phase == PagePipelinePhase.DRAWING_QA_FAILED or row.severity == "error":
        return "失败"
    if row.phase in {
        PagePipelinePhase.ASSET_MISSING,
        PagePipelinePhase.FALLBACK,
        PagePipelinePhase.SCHEMA_BLOCKED,
    } or row.severity == "warn":
        return "需注意"
    if row.phase in {
        PagePipelinePhase.QUEUED,
        PagePipelinePhase.GENERATING,
        PagePipelinePhase.BINDING_ASSETS,
        PagePipelinePhase.COMPILING_SCENE,
    } or row.severity == "info":
        return "进行中"
    return "待处理"


def status_badge(row: PagePipelineStatus) -> str:
    """Compact badge for navigator rows: mark + text label."""
    label = status_label(row)
    key = {
        "完成": "success",
        "失败": "error",
        "需注意": "warn",
        "进行中": "info",
    }.get(label, "neutral")
    meta = _severity_meta(key)
    return f"{meta['mark']}{label}"


def status_chip_html(row: PagePipelineStatus) -> str:
    """Colored bordered chip: mark + text (accessible beyond color alone)."""
    label = status_label(row)
    css_key = {
        "完成": "ok",
        "失败": "error",
        "需注意": "warn",
        "进行中": "info",
    }.get(label, "neutral")
    mark = {
        "ok": "✓",
        "error": "✕",
        "warn": "!",
        "info": "…",
        "neutral": "○",
    }[css_key]
    return (
        f'<span class="status-chip status-chip-{css_key}" '
        f'role="status" aria-label="{label}">'
        f'<span class="status-chip-mark" aria-hidden="true">{mark}</span>'
        f"{label}</span>"
    )


_PRIMARY_ACTION_PREFERENCE: tuple[PageStatusAction, ...] = (
    PageStatusAction.REBIND_ASSETS,
    PageStatusAction.RETRY,
    PageStatusAction.CHANGE_TEMPLATE,
    PageStatusAction.UNSKIP,
    PageStatusAction.OPEN_STUDIO,
    PageStatusAction.SKIP,
)


def load_page_status_board(
    presentation_id: UUID,
    *,
    workflow_step: str | None = None,
) -> PageStatusBoard:
    with get_session() as session:
        return PageStatusBoardService(session).build_board(
            presentation_id,
            workflow_step=workflow_step,
        )


def status_short_detail(row: PagePipelineStatus) -> str:
    label = row.status_label or PAGE_PHASE_LABELS.get(row.phase, "")
    if row.detail and row.severity in {"warn", "error"}:
        detail = row.detail.strip()
        if len(detail) > 18:
            detail = detail[:18] + "…"
        return detail
    return label


def pick_primary_action(actions: list[PageStatusAction]) -> PageStatusAction | None:
    if not actions:
        return None
    for preferred in _PRIMARY_ACTION_PREFERENCE:
        if preferred in actions:
            return preferred
    return actions[0]


def split_primary_and_more(
    actions: list[PageStatusAction],
) -> tuple[PageStatusAction | None, list[PageStatusAction]]:
    primary = pick_primary_action(actions)
    if primary is None:
        return None, []
    more = [action for action in actions if action != primary]
    return primary, more


def render_compact_page_actions(
    *,
    presentation_id: UUID,
    project_id: UUID | None,
    row: PagePipelineStatus,
    workflow_run_id: UUID | None = None,
    key_prefix: str = "page_status",
) -> None:
    """One primary CTA + optional more menu (avoids 5 equal-weight buttons)."""
    if not row.actions or row.slide_id is None:
        return
    primary, more = split_primary_and_more(list(row.actions))
    if primary is None:
        return

    cols = st.columns([3, 1] if more else [1])
    with cols[0]:
        if st.button(
            action_label(primary),
            key=f"{key_prefix}_{presentation_id}_{row.slide_id}_{primary.value}",
            use_container_width=True,
            type="primary",
        ):
            _handle_action(
                presentation_id=presentation_id,
                project_id=project_id,
                slide_id=row.slide_id,
                action=primary,
                workflow_run_id=workflow_run_id,
            )
    if more:
        with cols[1]:
            with st.popover("⋯"):
                for action in more:
                    if st.button(
                        action_label(action),
                        key=f"{key_prefix}_{presentation_id}_{row.slide_id}_more_{action.value}",
                        use_container_width=True,
                    ):
                        _handle_action(
                            presentation_id=presentation_id,
                            project_id=project_id,
                            slide_id=row.slide_id,
                            action=action,
                            workflow_run_id=workflow_run_id,
                        )


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
    """Render per-page status lines and compact recovery actions."""
    board = load_page_status_board(presentation_id, workflow_step=workflow_step)

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
        chip = status_chip_html(row)
        title_bit = f" · {row.title}" if row.title and not compact else ""
        # Chip carries mark + text + color + border; phase line stays textual.
        line = f"{chip} {row.display_line()}{title_bit}"
        if row.detail and not compact:
            line = f"{line}  \n  {row.detail}"
        elif row.detail and compact:
            line = f"{line} — {row.detail}"

        if compact:
            st.markdown(line, unsafe_allow_html=True)
            continue

        with st.container(border=True):
            st.markdown(line, unsafe_allow_html=True)
            render_compact_page_actions(
                presentation_id=presentation_id,
                project_id=project_id,
                row=row,
                workflow_run_id=workflow_run_id,
                key_prefix=key_prefix,
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
            toast="已打开 Studio，请在「布局」中更换模板。",
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
    message = toast or "正在打开工作室…"
    st.toast(message)
    try:
        from archium.ui.app_navigation import get_app_page
        from archium.ui.product_flow import product_studio_page_key

        st.switch_page(get_app_page(product_studio_page_key()))
    except Exception:
        st.info("请切换到「工作室」继续编辑该页。")
