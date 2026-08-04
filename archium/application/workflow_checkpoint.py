"""Shared helpers for persisting workflow checkpoints."""

from __future__ import annotations

from typing import Any

from archium.application.unit_of_work import SessionLike, session_of
from archium.application.workflow_progress import append_step_log
from archium.config.settings import Settings
from archium.domain.workflow import WorkflowRun


def finalize_run_state(run: WorkflowRun, state_snapshot: dict[str, Any]) -> None:
    """Merge snapshot into run state and append step log entries."""
    run.state = dict(state_snapshot)
    append_step_log(run.state)


def commit_workflow_checkpoint(session: SessionLike, settings: Settings | None = None) -> None:
    """Flush workflow progress without stealing the outer transaction boundary."""
    del settings
    session = session_of(session)
    session.flush()
