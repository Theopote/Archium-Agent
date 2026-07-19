"""Candidate layout switching for Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.label_map import entity_label
from archium.ui.layout_family_ui import (
    format_layout_family_label,
    layout_family_availability_status,
    layout_family_implemented,
)
from archium.domain.visual.layout import LayoutPlan
from archium.ui.visual_service import SlideVisualSnapshot, replan_slide, select_layout_candidate


def render_layout_candidates_panel(*, slide_snapshot: SlideVisualSnapshot | None, advanced: bool) -> None:
    """Render candidate layout list, replan, and issue summary for the current slide."""
    st.markdown("**版式候选**")
    if slide_snapshot is None:
        st.caption("请选择页面后再切换版式。")
        return

    slide_id = slide_snapshot.slide.id
    plan = slide_snapshot.layout_plan
    validation = slide_snapshot.validation

    issue_count = len(validation.issues) if validation is not None else 0
    valid = validation.valid if validation is not None else None
    if validation is not None:
        status = "通过" if valid else f"需修复（{issue_count} 项）"
        st.caption(f"版式质量：{validation.score:.2f} · {status}")
        if validation.issues:
            with st.expander("页面问题", expanded=valid is False):
                for issue in validation.issues[:8]:
                    st.write(f"- {issue.severity.value} · {issue.message}")

    action_cols = st.columns(2)
    with action_cols[0]:
        if st.button(
            "重新排版",
            use_container_width=True,
            key=f"studio_replan_{slide_id}",
        ):
            _run_replan(slide_id)
    with action_cols[1]:
        if st.button(
            "检查问题",
            use_container_width=True,
            key=f"studio_check_issues_{slide_id}",
        ):
            if validation is None:
                st.info("尚未生成版式，无法检查。")
            elif valid:
                st.success("当前页未发现需修复的版式问题。")
            else:
                st.warning(f"发现 {issue_count} 个版式问题，请查看上方列表。")

    candidates = slide_snapshot.candidates
    if not candidates:
        st.caption("暂无候选版式。点击「重新排版」生成多个方案。")
        return

    current_id = plan.id if plan is not None else None
    selectable: dict[str, LayoutPlan] = {}
    for candidate in candidates:
        if layout_family_implemented(candidate.layout_family):
            selectable[str(candidate.id)] = candidate

    if not selectable:
        st.warning("当前候选版式均尚未实现导出，请尝试重新排版。")
        return

    selected = st.selectbox(
        "选择候选版式",
        options=list(selectable.keys()),
        format_func=lambda value: _candidate_label(
            selectable[value],
            current_id=current_id,
        ),
        key=f"studio_candidate_select_{slide_id}",
    )
    if st.button(
        "切换到此版式",
        use_container_width=True,
        key=f"studio_select_plan_{slide_id}",
    ):
        try:
            with get_session() as session:
                select_layout_candidate(
                    session,
                    slide_id=slide_id,
                    layout_plan_id=UUID(selected),
                )
            st.success("已切换版式。")
            st.rerun()
        except (WorkflowError, ValueError) as exc:
            st.error(format_user_error(exc))

    unimplemented = len(candidates) - len(selectable)
    if unimplemented:
        st.caption(f"{unimplemented} 个候选属于「即将支持」版式类型，已从列表隐藏。")

    if advanced and plan is not None:
        st.caption(
            f"{entity_label('LayoutPlan', advanced=True)} · "
            f"{format_layout_family_label(plan.layout_family)} · "
            f"变体 {plan.layout_variant}"
        )


def _candidate_label(plan: LayoutPlan, *, current_id: UUID | None) -> str:
    family_label = format_layout_family_label(plan.layout_family, show_availability=False)
    availability = layout_family_availability_status(plan.layout_family)
    suffix = "（当前）" if current_id is not None and plan.id == current_id else ""
    return f"{family_label} · {plan.layout_variant} · {availability}{suffix}"


def _run_replan(slide_id: UUID) -> None:
    try:
        with st.spinner("正在重新生成候选版式…"), get_session() as session:
            replan_slide(session, slide_id=slide_id, preset=None, candidate_count=3)
        st.success("已重新生成候选版式。")
        st.rerun()
    except Exception as exc:
        st.error(format_user_error(exc))
