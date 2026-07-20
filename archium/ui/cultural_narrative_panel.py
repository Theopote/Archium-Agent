"""Streamlit panel for project cultural narrative plans."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.cultural_narrative_service import (
    is_cultural_village_scenario,
    validate_narrative,
)
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.database.session import get_session


def render_cultural_narrative_panel(project_id: UUID) -> None:
    st.markdown("#### 文化叙事计划")
    st.caption("文化名村/遗产类项目的结构化故事框架，供 Storyline 与 Outline 引用。")

    with get_session() as session:
        projects = ProjectRepository(session)
        project = projects.get_by_id(project_id)
        narratives = projects.list_cultural_narratives(project_id)

    if project is None:
        st.warning("项目不存在")
        return

    if not is_cultural_village_scenario(project=project) and not narratives:
        return

    if not narratives:
        st.info("尚未生成文化叙事计划。运行文化名村类汇报生成后将自动创建。")
        return

    plan = narratives[0]
    st.markdown(f"**核心故事：** {plan.central_story}")
    if plan.identity_keywords:
        st.markdown("**身份关键词：** " + " · ".join(plan.identity_keywords))

    cols = st.columns(4)
    cols[0].metric("历史事件", len(plan.historical_timeline))
    cols[1].metric("人物", len(plan.characters))
    cols[2].metric("空间节点", len(plan.places))
    cols[3].metric("传播主题", len(plan.communication_themes))

    issues = validate_narrative(plan)
    if issues:
        with st.expander(f"质量提示（{len(issues)}）", expanded=True):
            for issue in issues[:10]:
                st.markdown(f"- {issue}")

    if plan.unsupported_claims:
        with st.expander("待核实表述"):
            for claim in plan.unsupported_claims:
                st.markdown(f"- {claim}")

    if plan.historical_timeline:
        with st.expander("历史时间线"):
            for event in plan.historical_timeline:
                legend = "（传说）" if event.is_legend else ""
                st.markdown(f"- **{event.year_or_period}** {event.event}{legend}")

    if plan.communication_themes:
        with st.expander("传播主题"):
            for theme in plan.communication_themes:
                links = [
                    *theme.linked_characters,
                    *theme.linked_places,
                    *theme.linked_rituals,
                    *theme.linked_buildings,
                ]
                link_text = f" → {', '.join(links)}" if links else ""
                st.markdown(f"- {theme.theme}{link_text}")

    st.caption(f"版本 v{plan.version} · 状态 {plan.approval_status.value}")
