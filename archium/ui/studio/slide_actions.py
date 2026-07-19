"""Shared Studio slide action helpers for top bar and side panels."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.visual_service import SlideVisualSnapshot, replan_slide


def describe_slide_validation(slide_snapshot: SlideVisualSnapshot | None) -> tuple[str, str]:
    """Return (level, message) for slide layout validation: info|success|warning."""
    if slide_snapshot is None:
        return "info", "请先选择页面。"
    validation = slide_snapshot.validation
    if validation is None:
        return "info", "尚未生成版式，无法检查。"
    issue_count = len(validation.issues)
    if validation.valid:
        return "success", "当前页未发现需修复的版式问题。"
    return "warning", f"发现 {issue_count} 个版式问题，请在右侧「版式候选」查看详情。"


def run_studio_replan(slide_id: UUID) -> None:
    try:
        with st.spinner("正在重新生成候选版式…"), get_session() as session:
            replan_slide(session, slide_id=slide_id, preset=None, candidate_count=3)
        st.success("已重新生成候选版式。")
        st.rerun()
    except Exception as exc:
        st.error(format_user_error(exc))


def show_studio_validation_feedback(slide_snapshot: SlideVisualSnapshot | None) -> None:
    level, message = describe_slide_validation(slide_snapshot)
    if level == "success":
        st.success(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.info(message)
