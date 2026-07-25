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
    page_key_override: str | None = None,
) -> None:
    target = resolve_action_target(
        action,
        pending_fact_count=pending_fact_count,
        conflict_fact_count=conflict_fact_count,
    )
    apply_action_dispatch(session_state, target)
    from archium.ui.app_navigation import get_app_page

    page_key = page_key_override or target.page_key
    page_switcher(get_app_page(page_key))


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


def _maybe_start_orchestration(
    session,
    session_state: dict[str, Any],
    action: NextBestActionType,
    *,
    project_id: UUID,
    settings,
    target: ActionDispatch,
) -> str | None:
    """Start/resume orchestration when ActionDispatch requests it. Returns page override."""
    if target.orchestration_action not in {"start", "resume"} or settings is None:
        return None
    from archium.application.orchestration import WorkflowOrchestrationService
    from archium.application.context.project_context_builder import build_project_context
    from archium.infrastructure.llm.factory import create_llm_provider

    llm = create_llm_provider(settings)
    service = WorkflowOrchestrationService(session, llm, settings=settings)
    context = build_project_context(session, project_id)
    task = str(session_state.get("genesis_task_description") or "")
    if target.orchestration_action == "resume":
        active = service.get_active_run(project_id)
        if active is None:
            return None
        result = service.resume(active.id)
    else:
        result = service.start(
            project_id,
            context,
            action=action,
            user_task_description=task,
        )
    session_state["orchestration_run_id"] = str(result.workflow_run.id)
    session_state["orchestration_active_stage"] = (
        result.active_stage.value if result.active_stage else None
    )
    for warning in result.warnings[:3]:
        st.caption(warning)
    return result.page_key or target.page_key


def dispatch_next_best_action(
    session,
    session_state: dict[str, Any],
    action: NextBestActionType,
    *,
    project_id: UUID,
    settings=None,
    page_switcher=st.switch_page,
) -> bool:
    """Handle RESEARCH inline; optionally start orchestration; navigate."""
    if action == NextBestActionType.RESEARCH and settings is not None:
        with st.spinner("正在启动自主研究…"):
            if try_navigate_research_action(
                session,
                session_state,
                project_id,
                settings=settings,
                page_switcher=page_switcher,
            ):
                # Also open/resume an orchestration plan so durable stage state exists.
                pending, conflicts = pending_fact_counts(session, project_id)
                target = resolve_action_target(
                    action,
                    pending_fact_count=pending,
                    conflict_fact_count=conflicts,
                )
                _maybe_start_orchestration(
                    session,
                    session_state,
                    action,
                    project_id=project_id,
                    settings=settings,
                    target=target,
                )
                return True
        return False

    pending, conflicts = pending_fact_counts(session, project_id)
    target = resolve_action_target(
        action,
        pending_fact_count=pending,
        conflict_fact_count=conflicts,
    )
    page_override = None
    if settings is not None and target.orchestration_action in {"start", "resume"}:
        try:
            with st.spinner("正在启动工作编排…"):
                page_override = _maybe_start_orchestration(
                    session,
                    session_state,
                    action,
                    project_id=project_id,
                    settings=settings,
                    target=target,
                )
        except Exception as exc:  # noqa: BLE001 — navigation must still work
            st.caption(f"编排未启动（可稍后在任务页继续）：{exc}")

    navigate_next_best_action(
        session_state,
        action,
        project_id=project_id,
        pending_fact_count=pending,
        conflict_fact_count=conflicts,
        page_switcher=page_switcher,
        page_key_override=page_override,
    )
    return True


def workflow_entry_from_context(context) -> WorkflowEntryDispatch:
    pending = conflict = 0
    return resolve_workflow_entry(context, pending_fact_count=pending, conflict_fact_count=conflict)
