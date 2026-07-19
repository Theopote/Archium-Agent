"""Shared helpers for persisting workflow checkpoints."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from archium.application.workflow_progress import append_step_log
from archium.config.settings import Settings, get_settings
from archium.domain.workflow import WorkflowRun


def finalize_run_state(run: WorkflowRun, state_snapshot: dict[str, Any]) -> None:
    """Merge snapshot into run state and append step log entries."""
    run.state = dict(state_snapshot)
    append_step_log(run.state)


def commit_workflow_checkpoint(session: Session, settings: Settings | None = None) -> None:
    """Flush and optionally commit so other sessions (e.g. Streamlit) can poll."""
    resolved = settings or get_settings()
    session.flush()
    if resolved.workflow_checkpoint_commit_enabled:
        session.commit()
