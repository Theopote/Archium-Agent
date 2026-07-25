"""Navigate product pages from ProjectContext / NextBestAction."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import streamlit as st

from archium.application.context.next_action_selector import (
    resolve_action_target,
    resolve_workflow_entry,
)
from archium.application.context.types import ActionDispatch, WorkflowEntryDispatch
from archium.application.context.workflow_navigation import apply_workflow_entry
from archium.domain.intent.next_best_action import NextBestActionType


def pending_fact_counts(session, project_id: UUID) -> tuple[int, int]:
    from archium.application.fact_ledger_service import FactLedgerService

    try:
        ledger = FactLedgerService(session).get_ledger(project_id)
        return ledger.pending_count, ledger.conflict_count
    except Exception:
        return 0, 0


def apply_action_dispatch(session_state: dict[str, Any], target: ActionDispatch) -> None:
    if target.mission_step is not None:
        session_state["mission_step"] = target.mission_step
    if target.focus:
        session_state["materials_focus"] = target.focus


def navigate_workflow_entry(
    session_state: dict[str, Any],
    dispatch: WorkflowEntryDispatch,
    *,
    page_switcher=st.switch_page,
) -> None:
    apply_workflow_entry(session_state, dispatch)
    apply_action_dispatch(
        session_state,
        ActionDispatch(
            page_key=dispatch.page_key,
            mission_step=dispatch.mission_step,
            label=dispatch.label,
            focus=dispatch.focus,
        ),
    )
    from archium.ui.app_navigation import get_app_page

    page_switcher(get_app_page(dispatch.page_key))


def navigate_next_best_action(
    session_state: dict[str, Any],
    action: NextBestActionType,
    *,
    project_id: UUID,
    pending_fact_count: int = 0,
    conflict_fact_count: int = 0,
    page_switcher=st.switch_page,
) -> None:
    target = resolve_action_target(
        action,
        pending_fact_count=pending_fact_count,
        conflict_fact_count=conflict_fact_count,
    )
    apply_action_dispatch(session_state, target)
    from archium.ui.app_navigation import get_app_page

    page_switcher(get_app_page(target.page_key))


def try_navigate_research_action(
    session,
    session_state: dict[str, Any],
    project_id: UUID,
    *,
    settings,
    page_switcher=st.switch_page,
) -> bool:
    """Run autonomous research; navigate to mission step 2 on success."""
    from archium.application.context.context_analyzer import ContextAnalyzer
    from archium.infrastructure.llm.factory import create_llm_provider
    from archium.ui.app_navigation import get_app_page

    llm = create_llm_provider(settings)
    ok, message = ContextAnalyzer(session, llm, settings=settings).try_execute_research(
        project_id
    )
    if ok:
        session_state["mission_step"] = 2
        page_switcher(get_app_page("project-mission"))
        return True
    st.info(message)
    return False


def dispatch_next_best_action(
    session,
    session_state: dict[str, Any],
    action: NextBestActionType,
    *,
    project_id: UUID,
    settings=None,
    page_switcher=st.switch_page,
) -> bool:
    """Handle RESEARCH inline; otherwise navigate. Returns True if navigated."""
    if action == NextBestActionType.RESEARCH and settings is not None:
        with st.spinner("正在启动自主研究…"):
            if try_navigate_research_action(
                session,
                session_state,
                project_id,
                settings=settings,
                page_switcher=page_switcher,
            ):
                return True
        return False

    pending, conflicts = pending_fact_counts(session, project_id)
    navigate_next_best_action(
        session_state,
        action,
        project_id=project_id,
        pending_fact_count=pending,
        conflict_fact_count=conflicts,
        page_switcher=page_switcher,
    )
    return True


def workflow_entry_from_context(context) -> WorkflowEntryDispatch:
    pending = conflict = 0
    return resolve_workflow_entry(context, pending_fact_count=pending, conflict_fact_count=conflict)
