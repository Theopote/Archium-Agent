"""Project event log + job progress partner chrome."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.infrastructure.database.session import get_session


_EVENT_LABELS = {
    "project_created": "创建项目",
    "context_updated": "理解更新",
    "mission_changed": "任务变化",
    "intent_changed": "意图变化",
    "concept_selected": "选定方向",
    "research_completed": "研究完成",
    "design_revised": "设计修订",
    "design_critique": "设计批评",
    "design_decision": "设计决策",
    "reflection": "设计反思",
    "visual_feedback": "示意反馈",
    "presentation_generated": "汇报生成",
    "process_checkpoint": "过程节点",
    "other": "其他",
}


def render_project_event_log(
    project_id: UUID,
    *,
    limit: int = 8,
    expanded: bool = False,
    title: str = "项目事件记忆",
) -> None:
    """Unified ProjectEvent strip (IntentEvolution / process projections)."""
    try:
        from archium.application.project_event_service import ProjectEventService

        with get_session() as session:
            events = ProjectEventService(session).list_for_project(
                project_id, limit=limit
            )
    except Exception:
        return
    if not events:
        return
    with st.expander(title, expanded=expanded):
        st.caption("跨理解 / 意图 / 过程的统一记忆（非完整 Event Sourcing）。")
        for event in events:
            label = _EVENT_LABELS.get(event.event_type.value, event.event_type.value)
            when = event.at.astimezone().strftime("%m-%d %H:%M")
            st.markdown(f"- **{label}** · `{when}` — {event.display_line()}")


def render_job_progress_strip(
    project_id: UUID,
    *,
    limit: int = 5,
    active_only: bool = True,
    title: str = "后台任务",
) -> None:
    """Unified WorkflowRun + ArtifactJob progress."""
    try:
        from archium.application.job_progress_service import JobProgressService

        with get_session() as session:
            jobs = JobProgressService(session).list_for_project(
                project_id, limit=limit, active_only=active_only
            )
    except Exception:
        return
    if not jobs:
        return
    st.markdown(f"**{title}**")
    for job in jobs:
        pct = job.progress_pct
        if pct is not None:
            st.progress(min(1.0, max(0.0, pct / 100.0)), text=job.display_line())
        else:
            st.caption(job.display_line())
        if job.message:
            st.caption(job.message)
