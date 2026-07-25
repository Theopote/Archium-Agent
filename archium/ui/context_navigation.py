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
    mission_step_override: int | None = None,
    focus_override: str | None = None,
) -> None:
    target = resolve_action_target(
        action,
        pending_fact_count=pending_fact_count,
        conflict_fact_count=conflict_fact_count,
    )
    if mission_step_override is not None:
        target = ActionDispatch(
            page_key=target.page_key,
            mission_step=mission_step_override,
            label=target.label,
            focus=focus_override if focus_override is not None else target.focus,
            orchestration_action=target.orchestration_action,
            stage_hint=target.stage_hint,
        )
    elif focus_override is not None:
        target = ActionDispatch(
            page_key=target.page_key,
            mission_step=target.mission_step,
            label=target.label,
            focus=focus_override,
            orchestration_action=target.orchestration_action,
            stage_hint=target.stage_hint,
        )
    apply_action_dispatch(session_state, target)
    from archium.ui.app_navigation import get_app_page

    page_key = page_key_override or target.page_key
    page_switcher(get_app_page(page_key))


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
    force_navigate: bool = False,
):
    """Execute runnable NBA work (Act), then navigate or stay for Reassess (Learn).

    Returns ``NbaExecutionResult`` when settings are available; ``True`` for
    navigate-only fallback without settings.
    """
    from archium.application.context.nba_action_executor import (
        NbaActionExecutor,
        NbaExecutionResult,
    )
    from archium.infrastructure.llm.factory import create_llm_provider

    pending, conflicts = pending_fact_counts(session, project_id)
    task = str(
        session_state.get("genesis_task_description")
        or session_state.get("mission_task_description")
        or ""
    )

    if settings is None:
        # Navigate-only fallback when settings unavailable
        navigate_next_best_action(
            session_state,
            action,
            project_id=project_id,
            pending_fact_count=pending,
            conflict_fact_count=conflicts,
            page_switcher=page_switcher,
        )
        return True

    llm = create_llm_provider(settings)
    spinner_labels = {
        NextBestActionType.RESEARCH: "正在执行自主研究…",
        NextBestActionType.EXPLORE_DIRECTIONS: "正在推演概念方向…",
        NextBestActionType.GENERATE_MISSION: "正在生成任务理解…",
    }
    label = spinner_labels.get(action, "正在执行下一步…")
    with st.spinner(label):
        result: NbaExecutionResult = NbaActionExecutor(
            session, llm, settings=settings
        ).execute(
            project_id,
            action,
            user_task_description=task,
            pending_fact_count=pending,
            conflict_fact_count=conflicts,
        )

    if result.message:
        if result.success and result.executed:
            st.success(result.message)
        elif not result.success:
            st.warning(result.message)
        else:
            st.info(result.message)
    for warning in result.warnings[:3]:
        if warning and warning != result.message:
            st.caption(warning)

    page_override = result.page_key
    if (
        result.success
        and result.orchestration_action in {"start", "resume"}
        and not result.stay_after_execute
    ):
        target = ActionDispatch(
            page_key=result.page_key or "project-mission",
            mission_step=result.mission_step,
            focus=result.focus,
            orchestration_action=result.orchestration_action,
            stage_hint=result.stage_hint,
        )
        try:
            with st.spinner("正在同步工作编排…"):
                orch_page = _maybe_start_orchestration(
                    session,
                    session_state,
                    action,
                    project_id=project_id,
                    settings=settings,
                    target=target,
                )
            if orch_page:
                page_override = orch_page
        except Exception as exc:  # noqa: BLE001
            st.caption(f"编排未启动（可稍后在任务页继续）：{exc}")

    should_nav = force_navigate or result.should_navigate
    if should_nav and page_override:
        navigate_next_best_action(
            session_state,
            action,
            project_id=project_id,
            pending_fact_count=pending,
            conflict_fact_count=conflicts,
            page_switcher=page_switcher,
            page_key_override=page_override,
            mission_step_override=result.mission_step,
            focus_override=result.focus,
        )
    elif result.stay_after_execute and result.success and result.executed:
        session_state["nba_last_loop"] = {
            "action": action.value,
            "message": result.message,
            "reassessed": result.reassessed,
        }

    return result
