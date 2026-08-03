"""Product-facing copy for workflow resume / continue (WF-004)."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.ui.app_navigation import get_app_page
from archium.ui.error_handlers import report_user_error

RESUME_EXPORT_BUTTON_LABEL = "从审核门继续导出"
RESUME_EXPORT_HELP = (
    "仅在仍有待确认审核门时可继续。"
    "若已结束或无可恢复节点，请到「生成」开新一轮，不要期望从起点静默重跑。"
)
RESUME_EXPORT_STARTED = "已在后台从审核门继续，请查看进度。"


def is_no_checkpoint_resume_error(exc: BaseException) -> bool:
    text = str(exc)
    return "WF-004" in text or "无可恢复的 interrupt" in text or "拒绝从 START 重跑" in text


def render_resume_failure(
    exc: BaseException,
    *,
    project_id: UUID | None = None,
) -> None:
    """Map WF-004 / generic resume failures to product CTAs."""
    if is_no_checkpoint_resume_error(exc):
        st.error(
            "当前没有可继续的审核门，无法从中途恢复导出。"
            "请到「生成」开新一轮，或在有待确认审核时再继续。"
        )
        cols = st.columns(2)
        with cols[0]:
            st.page_link(get_app_page("generate"), label="去「生成」开新一轮")
        with cols[1]:
            st.page_link(get_app_page("edit"), label="回工作室编辑")
        if project_id is not None:
            st.caption(f"项目：`{project_id}`")
        return
    st.error(report_user_error(exc))
