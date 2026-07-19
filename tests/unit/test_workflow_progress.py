"""Unit tests for workflow progress helpers."""

from __future__ import annotations

from uuid import uuid4

from archium.application.workflow_progress import (
    append_step_log,
    infer_workflow_kind,
    label_for_step,
    progress_fraction,
    snapshot_from_run,
)
from archium.domain.enums import WorkflowStatus, WorkflowStep
from archium.domain.workflow import WorkflowRun


def test_append_step_log_deduplicates_consecutive_steps() -> None:
    state = {"current_step": WorkflowStep.BRIEF.value}
    append_step_log(state)
    append_step_log(state)
    assert len(state["step_log"]) == 1

    state["current_step"] = WorkflowStep.STORYLINE.value
    append_step_log(state)
    assert len(state["step_log"]) == 2
    assert state["step_log"][-1]["step"] == WorkflowStep.STORYLINE.value


def test_label_for_step_storyline() -> None:
    assert "叙事结构" in label_for_step(WorkflowStep.STORYLINE.value)


def test_label_for_step_repair_slides_with_index() -> None:
    label = label_for_step(
        WorkflowStep.REPAIR_SLIDES.value,
        state={"repair_slide_index": 2},
    )
    assert "第 3 页" in label


def test_label_for_step_visual_critique_with_plans() -> None:
    label = label_for_step(
        WorkflowStep.VISUAL_CRITIQUE.value,
        state={"layout_plans": [{}, {}, {}]},
    )
    assert "3 页" in label


def test_snapshot_from_run_includes_step_log() -> None:
    run = WorkflowRun(
        id=uuid4(),
        project_id=uuid4(),
        status=WorkflowStatus.RUNNING,
        state={
            "current_step": WorkflowStep.SLIDES.value,
            "step_log": [
                {"step": WorkflowStep.BRIEF.value, "at": "2026-01-01T00:00:00+00:00"},
                {"step": WorkflowStep.SLIDES.value, "at": "2026-01-01T00:01:00+00:00"},
            ],
        },
    )
    snapshot = snapshot_from_run(run)
    assert snapshot.current_step == WorkflowStep.SLIDES.value
    assert len(snapshot.step_log) == 2
    assert snapshot.is_terminal is False
    assert 0.0 < snapshot.progress_fraction < 1.0


def test_infer_workflow_kind_from_step_prefix() -> None:
    assert infer_workflow_kind(WorkflowStep.VISUAL_VALIDATE_LAYOUTS.value) == "visual"
    assert infer_workflow_kind(WorkflowStep.PLANNING_WORKSTREAMS.value) == "planning"
    assert infer_workflow_kind(WorkflowStep.BRIEF.value) == "presentation"


def test_progress_fraction_completed_run() -> None:
    fraction = progress_fraction(
        WorkflowStep.FINALIZE.value,
        status=WorkflowStatus.COMPLETED,
    )
    assert fraction == 1.0
