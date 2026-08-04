"""Apply ProjectContext workflow entry to Streamlit session state."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, cast
from uuid import UUID

from archium.application.context.next_action_selector import resolve_workflow_entry
from archium.application.context.project_context_builder import build_project_context
from archium.application.context.types import WorkflowEntryDispatch
from archium.application.fact_ledger_service import FactLedgerService
from archium.application.unit_of_work import SessionLike, session_of

# Streamlit SessionStateProxy is dict-like at runtime; stubs disagree with Protocol.get.
SessionStateLike = MutableMapping[str, Any]


def as_session_state(state: object) -> SessionStateLike:
    """Narrow Streamlit session_state / dict to a mutable mapping for helpers."""
    return cast(SessionStateLike, state)


def workflow_entry_for_project(
    session: SessionLike,
    project_id: UUID,
) -> WorkflowEntryDispatch | None:
    session = session_of(session)
    context = build_project_context(session, project_id)
    if context is None:
        return None
    ledger = FactLedgerService(session).get_ledger(project_id)
    return resolve_workflow_entry(
        context,
        pending_fact_count=ledger.pending_count,
        conflict_fact_count=ledger.conflict_count,
    )


def apply_workflow_entry(session_state: SessionStateLike, dispatch: WorkflowEntryDispatch) -> None:
    if dispatch.mission_step is not None:
        session_state["mission_step"] = dispatch.mission_step
    if dispatch.focus:
        session_state["materials_focus"] = dispatch.focus
    session_state["context_workflow_entry"] = {
        "page_key": dispatch.page_key,
        "mission_step": dispatch.mission_step,
        "workflow": dispatch.workflow.value if dispatch.workflow else None,
        "label": dispatch.label,
    }


def sync_mission_step_from_context(session: SessionLike, project_id: UUID, session_state: SessionStateLike) -> None:
    """On mission page load, jump to the step implied by ProjectContext when unset."""
    session = session_of(session)
    if session_state.get("mission_step", 1) > 1:
        return
    entry = workflow_entry_for_project(session, project_id)
    if entry is None or entry.page_key != "project-mission":
        return
    if entry.mission_step is not None and entry.mission_step > 1:
        session_state["mission_step"] = entry.mission_step
