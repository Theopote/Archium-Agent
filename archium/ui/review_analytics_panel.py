"""Project-level review quality dashboard keyed by rule_code."""

from __future__ import annotations

from uuid import UUID

import pandas as pd
import streamlit as st

from archium.application.review_analytics import summarize_rule_codes
from archium.application.review_service import PresentationReviewService
from archium.domain.enums import ReviewStatus
from archium.domain.review import ReviewIssue
from archium.infrastructure.database.session import get_session
from archium.ui.workspace_service import list_project_presentations

REPAIR_STRATEGY_LABELS = {
    "tiered_layout": "分层版面修复",
    "llm_content": "LLM 内容修复",
    "manual": "人工确认",
    "none": "无自动策略",
}


def _format_dismiss_rate(rate: float | None) -> str:
    if rate is None:
        return "—"
    return f"{rate * 100:.0f}%"


def render_rule_code_stats(issues: list[ReviewIssue]) -> None:
    """Render rule_code hit-rate and dismiss-rate table."""
    stats = summarize_rule_codes(issues)
    if not stats:
        st.caption("暂无 rule_code 统计数据。")
        return

    rows = [
        {
            "rule_code": item.rule_code,
            "命中数": item.total,
            "待处理": item.open,
            "已解决": item.resolved,
            "已忽略": item.dismissed,
            "误报率(忽略占比)": _format_dismiss_rate(item.dismiss_rate),
            "修复策略": REPAIR_STRATEGY_LABELS.get(item.repair_strategy, item.repair_strategy),
        }
        for item in stats
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        "误报率以「已忽略 / (已解决 + 已忽略)」估算，仅作规则调优参考。"
    )


def render_project_review_quality_dashboard(project_id: UUID) -> None:
    """Aggregate review issues across all presentations in a project."""
    with get_session() as session:
        presentations = list_project_presentations(session, project_id)
        review_service = PresentationReviewService(session)
        all_issues = review_service.list_review_issues_by_project(project_id)

    st.markdown("#### 质量规则概览")
    st.caption("按 rule_code 汇总本项目全部汇报的自动审核结果，用于规则命中率与误报分析。")

    if not presentations:
        st.caption("生成汇报后将在此显示项目级质量统计。")
        return

    if not all_issues:
        st.caption("暂无审核问题。运行完整工作流后将在此显示规则命中统计。")
        return

    presentation_options = {"全部汇报": None}
    for presentation in presentations:
        presentation_options[presentation.title] = presentation.id

    selected_label = st.selectbox(
        "汇报范围",
        options=list(presentation_options.keys()),
        key=f"project_review_scope_{project_id}",
    )
    selected_presentation_id = presentation_options[selected_label]
    issues = (
        all_issues
        if selected_presentation_id is None
        else [issue for issue in all_issues if issue.presentation_id == selected_presentation_id]
    )

    if not issues:
        st.caption("所选汇报暂无审核问题。")
        return

    stats = summarize_rule_codes(issues)
    open_count = sum(1 for issue in issues if issue.status == ReviewStatus.OPEN)
    high_dismiss_rules = sum(
        1
        for item in stats
        if item.dismiss_rate is not None and item.dismiss_rate >= 0.5 and item.acted_count >= 2
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("审核问题", len(issues))
    col2.metric("待处理", open_count)
    col3.metric("规则种类", len(stats))
    col4.metric("高误报规则", high_dismiss_rules, help="忽略占比 ≥ 50% 且已有 ≥ 2 次人工处理")

    render_rule_code_stats(issues)
