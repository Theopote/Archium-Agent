"""Project knowledge profile UI — continuous spectrum, not mode selection."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.project_knowledge_display import (
    ProjectKnowledgeDisplay,
    build_project_knowledge_display,
)
from archium.domain.intent.knowledge_state import KnowledgeState


def load_project_knowledge_display(project_id: UUID) -> ProjectKnowledgeDisplay | None:
    from archium.application.project_context_builder import build_project_context
    from archium.infrastructure.database.session import get_session

    with get_session() as session:
        context = build_project_context(session, project_id)
    if context is None:
        return None
    return build_project_knowledge_display(context)


def render_project_knowledge_strip(
    project_id: UUID,
    *,
    compact: bool = False,
    show_known_unknown: bool = True,
) -> ProjectKnowledgeDisplay | None:
    """Primary knowledge-first chrome — use instead of workspace mode titles."""
    from archium.application.project_context_builder import build_project_context
    from archium.infrastructure.database.repositories import ProjectRepository
    from archium.infrastructure.database.session import get_session

    with get_session() as session:
        context = build_project_context(session, project_id)
        project = ProjectRepository(session).get_by_id(project_id)
    if context is None:
        return None
    display = build_project_knowledge_display(context)

    st.info(display.headline)
    if not compact:
        st.caption(display.caption)
        st.caption(f"当前重心：{display.focus} · 把握度约 {display.confidence_pct}%")

    if show_known_unknown and project is not None and project.knowledge_state is not None:
        _render_known_unknown(project.knowledge_state, compact=compact)
    return display


def render_project_knowledge_action_buttons(
    project_id: UUID,
    *,
    key_prefix: str,
    max_items: int = 3,
    settings=None,
) -> None:
    """Clickable NBA buttons wired to context navigation."""
    from archium.application.context.next_action_selector import resolve_action_target
    from archium.application.project_context_builder import build_project_context
    from archium.infrastructure.database.session import get_session
    from archium.ui.context_navigation import (
        dispatch_next_best_action,
        pending_fact_counts,
    )
    from archium.ui.llm_settings import get_ui_effective_settings

    with get_session() as session:
        context = build_project_context(session, project_id)
        if context is None or not context.next_actions:
            display = load_project_knowledge_display(project_id)
            if display is not None:
                render_project_knowledge_actions(display, key_prefix=key_prefix, max_items=max_items)
            return
        pending, conflicts = pending_fact_counts(session, project_id)
        actions = context.next_actions[:max_items]

    st.caption("建议下一步")
    runtime_settings = settings or get_ui_effective_settings()
    cols = st.columns(len(actions))
    for index, action in enumerate(actions):
        target = resolve_action_target(
            action.action,
            pending_fact_count=pending,
            conflict_fact_count=conflicts,
        )
        label = target.label or action.reason or action.action.value
        with cols[index]:
            if st.button(label, key=f"{key_prefix}_nba_{index}_{action.action.value}", use_container_width=True):
                with get_session() as session:
                    dispatch_next_best_action(
                        session,
                        st.session_state,
                        action.action,
                        project_id=project_id,
                        settings=runtime_settings,
                    )


def render_project_knowledge_actions(
    display: ProjectKnowledgeDisplay,
    *,
    key_prefix: str,
    max_items: int = 3,
) -> None:
    if not display.suggested_actions:
        return
    st.caption("建议下一步")
    cols = st.columns(min(max_items, len(display.suggested_actions)))
    for index, action in enumerate(display.suggested_actions[:max_items]):
        cols[index % len(cols)].markdown(f"{index + 1}. {action}")


def _render_known_unknown(state: KnowledgeState, *, compact: bool) -> None:
    counts: list[str] = []
    if state.source_count:
        counts.append(f"来源 {state.source_count}")
    if state.fact_count:
        counts.append(f"事实 {state.fact_count}")
    if counts:
        st.caption(" · ".join(counts))
    if state.known:
        known_text = "；".join(f"{key}={value}" for key, value in list(state.known.items())[:6])
        if compact:
            st.caption(f"已知：{known_text}")
        else:
            st.markdown(f"**已知**：{known_text}")
    unknowns = state.unknown or state.missing_information
    if unknowns:
        text = "；".join(unknowns[:6])
        if compact:
            st.caption(f"仍缺：{text}")
        else:
            st.markdown(f"**仍缺**：{text}")
