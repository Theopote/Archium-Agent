"""Unit tests for workflow checkpoint commit helper."""

from __future__ import annotations

from uuid import uuid4

from archium.application.workflow_checkpoint import finalize_run_state
from archium.domain.enums import WorkflowStatus, WorkflowStep
from archium.domain.workflow import WorkflowRun


def test_finalize_run_state_appends_step_log() -> None:
    run = WorkflowRun(id=uuid4(), project_id=uuid4(), status=WorkflowStatus.RUNNING, state={})
    finalize_run_state(run, {"current_step": WorkflowStep.BRIEF.value})
    assert run.state["current_step"] == WorkflowStep.BRIEF.value
    assert run.state["step_log"][0]["step"] == WorkflowStep.BRIEF.value
