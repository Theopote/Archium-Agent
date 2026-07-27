"""WF-004 — resume must not replay from START without a checkpoint."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from archium.exceptions import WorkflowError
from archium.workflow.resume_policy import (
    ensure_resumable_checkpoint,
    snapshot_looks_resumable,
)


def test_snapshot_looks_resumable_when_next_pending() -> None:
    assert snapshot_looks_resumable(SimpleNamespace(next=("export_json",), tasks=()))
    assert not snapshot_looks_resumable(SimpleNamespace(next=(), tasks=()))
    assert not snapshot_looks_resumable(None)


def test_snapshot_looks_resumable_when_interrupt_task() -> None:
    task = SimpleNamespace(interrupts=(SimpleNamespace(value=True),))
    assert snapshot_looks_resumable(SimpleNamespace(next=(), tasks=(task,)))


def test_ensure_resumable_checkpoint_raises_without_interrupt() -> None:
    run_id = uuid4()
    with pytest.raises(WorkflowError, match="WF-004"):
        ensure_resumable_checkpoint(
            workflow_run_id=run_id,
            status="failed",
            resumable=False,
        )


def test_ensure_resumable_checkpoint_passes_when_resumable() -> None:
    ensure_resumable_checkpoint(
        workflow_run_id=uuid4(),
        status="running",
        resumable=True,
    )


def test_presentation_resume_no_longer_clears_and_replays_start() -> None:
    source = (
        __import__("pathlib").Path("archium/application/presentation_workflow_service.py")
        .read_text(encoding="utf-8")
    )
    # Gate + checkpoint path only; must not wipe thread then rebuild initial_state.
    assert "ensure_resumable_checkpoint" in source
    assert "clear_thread" not in source.split("def resume(")[1].split("def get_run(")[0]


def test_planning_and_visual_resume_guard_start_replay() -> None:
    planning = (
        __import__("pathlib").Path("archium/application/planning_workflow_service.py")
        .read_text(encoding="utf-8")
    )
    visual = (
        __import__("pathlib").Path("archium/application/visual/visual_workflow_service.py")
        .read_text(encoding="utf-8")
    )
    assert "ensure_resumable_checkpoint" in planning
    assert "ensure_resumable_checkpoint" in visual
    planning_resume = planning.split("def resume(")[1].split("def get_run(")[0]
    assert "initial_planning_state" not in planning_resume
    visual_resume = visual.split("def resume(")[1].split("def _to_result(")[0]
    assert "initial_visual_workflow_state" not in visual_resume
