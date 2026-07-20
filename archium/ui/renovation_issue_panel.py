"""Streamlit panel for renovation issue maps."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.renovation_issue_service import is_renovation_scenario, validate_issue_map
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.database.session import get_session


def render_renovation_issue_panel(project_id: UUID) -> None:
    st.markdown("#### 改造问题图")
    st.caption("老旧建筑改造类项目的证据 → 问题 → 策略闭环，供 Storyline 与 Outline 引用。")

    with get_session() as session:
        projects = ProjectRepository(session)
        project = projects.get_by_id(project_id)
        issue_maps = projects.list_renovation_issue_maps(project_id)

    if project is None:
        st.warning("项目不存在")
        return

    if not is_renovation_scenario(project=project) and not issue_maps:
        return

    if not issue_maps:
        st.info("尚未生成改造问题图。运行老旧建筑改造类汇报生成后将自动创建。")
        return

    plan = issue_maps[0]
    st.markdown(f"**建筑概况：** {plan.building_summary}")
    if plan.condition_overview:
        st.markdown(f"**现状概述：** {plan.condition_overview}")

    cols = st.columns(3)
    cols[0].metric("证据项", len(plan.evidence_items))
    cols[1].metric("问题", len(plan.issues))
    cols[2].metric("策略", len(plan.strategies))

    issues = validate_issue_map(plan)
    if issues:
        with st.expander(f"质量提示（{len(issues)}）", expanded=True):
            for issue in issues[:10]:
                st.markdown(f"- {issue}")

    if plan.unsupported_claims:
        with st.expander("待核实表述"):
            for claim in plan.unsupported_claims:
                st.markdown(f"- {claim}")

    if plan.issues:
        with st.expander("问题与证据关联"):
            evidence_by_id = {item.id: item for item in plan.evidence_items}
            for renovation_issue in plan.issues:
                refs = [
                    evidence_by_id[eid].description[:50]
                    for eid in renovation_issue.linked_evidence_ids
                    if eid in evidence_by_id
                ]
                ref_text = f"（证据：{'; '.join(refs)}）" if refs else ""
                st.markdown(
                    f"- **[{renovation_issue.category}]** {renovation_issue.problem_statement} "
                    f"_{renovation_issue.severity}_{ref_text}"
                )

    if plan.strategies:
        with st.expander("策略与问题关联"):
            for strategy in plan.strategies:
                st.markdown(
                    f"- **{strategy.title}** → 问题 {', '.join(strategy.linked_issue_ids)}"
                )
                st.caption(strategy.approach)

    st.caption(f"版本 v{plan.version} · 状态 {plan.approval_status.value}")
