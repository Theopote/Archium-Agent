"""Render product QA as three actionable buckets (事实 / 表达 / 渲染)."""

from __future__ import annotations

import streamlit as st

from archium.domain.product_qa_bucket import (
    ProductQaBucketSummary,
    ProductQaFinding,
    collect_product_qa_from_sources,
    group_product_qa_findings,
)


def render_product_qa_buckets(
    findings: list[ProductQaFinding],
    *,
    title: str = "问题分类",
    empty_caption: str = "暂无分类问题。",
    limit_per_bucket: int = 6,
) -> list[ProductQaBucketSummary]:
    """Show fact / expression / render queues instead of one mixed score."""
    summaries = group_product_qa_findings(findings, limit_per_bucket=limit_per_bucket)
    total = sum(item.count for item in summaries)
    st.markdown(f"**{title}**")
    if total == 0:
        st.caption(empty_caption)
        return summaries

    from archium.ui.components.chrome import render_stat_chips

    render_stat_chips(
        [
            (
                summary.label,
                str(summary.count),
                "error" if summary.count else "ok",
            )
            for summary in summaries
        ]
    )
    cols = st.columns(3)
    for column, summary in zip(cols, summaries, strict=True):
        with column:
            st.caption(summary.caption)
            if not summary.findings:
                st.caption("无")
                continue
            for finding in summary.findings:
                head = finding.title
                if finding.rule_code:
                    head = f"`{finding.rule_code}` · {finding.title}"
                line = f"- {head}"
                if finding.severity:
                    line = f"- **{finding.severity}** · {head}"
                st.markdown(line)
                if finding.detail:
                    st.caption(finding.detail[:160])
    return summaries


def render_product_qa_from_reports(
    *,
    review_issues: list[dict] | None = None,
    deck_qa_report: dict | None = None,
    critic_report: dict | None = None,
    quality_issues: list[dict] | None = None,
    title: str = "问题分类（事实 / 表达 / 渲染）",
) -> list[ProductQaBucketSummary]:
    findings = collect_product_qa_from_sources(
        review_issues=review_issues,
        deck_qa_report=deck_qa_report,
        critic_report=critic_report,
        quality_issues=quality_issues,
    )
    return render_product_qa_buckets(findings, title=title)
