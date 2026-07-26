"""Partner critique summary cards — Design / Presentation / Visual findings."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import streamlit as st

from archium.infrastructure.database.session import get_session


def render_visual_critic_findings(critic: dict[str, Any] | None) -> None:
    """Show actionable Visual Critic findings (not score-only)."""
    if not isinstance(critic, dict):
        return
    total = critic.get("total_score")
    score_label = f"{total:.2f}" if isinstance(total, (int, float)) else "—"
    st.markdown(f"**视觉批判** · 评分 {score_label}")
    findings = critic.get("findings") or []
    if not isinstance(findings, list) or not findings:
        st.caption("暂无具体发现。")
        return
    for item in findings[:8]:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "warning")
        message = str(item.get("message") or "").strip()
        suggestion = str(item.get("suggestion") or "").strip()
        code = str(item.get("rule_code") or "").strip()
        if not message:
            continue
        head = f"`{code}` · {severity}" if code else severity
        st.markdown(f"- **{head}** — {message}")
        if suggestion:
            st.caption(f"建议：{suggestion}")


def render_design_critique_card(
    report: dict[str, Any] | None = None,
    *,
    title: str = "设计批判",
    project_id: UUID | None = None,
) -> None:
    """Render DesignCritiqueReport (dict); hydrate from IntentEvolution when needed."""
    data = report
    if data is None:
        raw = st.session_state.get("last_design_critique_report")
        data = raw if isinstance(raw, dict) else None
    if (not isinstance(data, dict) or not data) and project_id is not None:
        try:
            from archium.application.design_revise_persistence import (
                design_critique_resume_page,
                load_latest_design_critique_report,
            )

            with get_session() as session:
                data = load_latest_design_critique_report(session, project_id)
            if isinstance(data, dict) and data:
                st.session_state["last_design_critique_report"] = data
        except Exception:
            data = None
    if not isinstance(data, dict) or not data:
        return
    with st.expander(title, expanded=False):
        verdict = str(data.get("verdict") or "caution")
        summary = str(data.get("summary") or "").strip()
        st.caption(f"裁决：{verdict}")
        if summary:
            st.markdown(summary)
        for label, key in (
            ("弱点", "weaknesses"),
            ("缺证据", "missing_evidence"),
            ("替代方向", "alternative_directions"),
        ):
            items = data.get(key) or []
            if not isinstance(items, list) or not items:
                continue
            st.markdown(f"**{label}**")
            for item in items[:5]:
                text = item.get("text") if isinstance(item, dict) else str(item)
                if text:
                    st.markdown(f"- {text}")
        resume = None
        try:
            from archium.application.design_revise_persistence import (
                design_critique_resume_page,
            )

            resume = design_critique_resume_page(data)
        except Exception:
            resume = None
        if resume:
            from archium.ui.app_navigation import get_app_page

            st.page_link(get_app_page(resume), label="回概念探索处理批判 →")


def render_presentation_critique_card(
    presentation_id: UUID | None = None,
    *,
    title: str = "汇报批判摘要",
) -> None:
    """Compute or load PresentationCritiqueReport for Deliver / Studio."""
    report_dict: dict[str, Any] | None = None
    raw = st.session_state.get("last_presentation_critique")
    if isinstance(raw, dict):
        report_dict = raw
    if report_dict is None and presentation_id is not None:
        try:
            report_dict = _compute_presentation_critique(presentation_id)
            if report_dict:
                st.session_state["last_presentation_critique"] = report_dict
        except Exception:
            report_dict = None
    if not report_dict:
        return
    with st.expander(title, expanded=False):
        st.caption(
            "故事 {story:.0%} · 视觉 {visual:.0%} · 建筑表达 {arch:.0%}".format(
                story=float(report_dict.get("story_strength") or 0),
                visual=float(report_dict.get("visual_quality") or 0),
                arch=float(report_dict.get("architectural_expression") or 0),
            )
        )
        for label, key in (
            ("缺失", "missing_points"),
            ("建议", "suggestions"),
            ("过载页", "overloaded_slides"),
        ):
            items = report_dict.get(key) or []
            if not isinstance(items, list) or not items:
                continue
            st.markdown(f"**{label}**")
            for item in items[:6]:
                st.markdown(f"- {item}")


def _compute_presentation_critique(presentation_id: UUID) -> dict[str, Any] | None:
    from archium.application.presentation_critic import critique_presentation
    from archium.infrastructure.database.repositories import PresentationRepository

    with get_session() as session:
        repo = PresentationRepository(session)
        presentation = repo.get_presentation(presentation_id)
        if presentation is None:
            return None
        brief = None
        if presentation.current_brief_id:
            brief = repo.get_brief(presentation.current_brief_id)
        storyline = None
        if presentation.current_storyline_id:
            storyline = repo.get_storyline(presentation.current_storyline_id)
        slides = repo.list_slides(presentation_id)
        report = critique_presentation(brief=brief, storyline=storyline, slides=slides)
        return report.as_dict()
