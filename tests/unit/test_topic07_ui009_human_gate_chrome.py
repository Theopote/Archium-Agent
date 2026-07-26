"""Topic 07 UI-009 — HumanGate helpers for five-stage chrome."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.enums import WorkflowStatus
from archium.domain.orchestration import (
    HumanGate,
    HumanGateKind,
    OrchestrationPlan,
    OrchestrationStage,
    OrchestrationStageSpec,
    OrchestrationStageStatus,
)
from archium.domain.workflow import WorkflowRun
from archium.ui.components.orchestration_status import (
    human_gate_caption,
    parse_human_gate,
    should_show_compact_gate,
)


def _run_with_gate(
    *,
    gate: HumanGate | None,
    stage_status: OrchestrationStageStatus = OrchestrationStageStatus.AWAITING_USER,
) -> WorkflowRun:
    project_id = uuid4()
    plan = OrchestrationPlan(
        project_id=project_id,
        stages=[
            OrchestrationStageSpec(
                stage=OrchestrationStage.MISSION_PLANNING,
                status=stage_status,
            )
        ],
        active_index=0,
    )
    state: dict = {"orchestration_plan": plan.model_dump(mode="json")}
    if gate is not None:
        state["human_gate"] = gate.as_dict()
    return WorkflowRun(
        project_id=project_id,
        status=WorkflowStatus.AWAITING_REVIEW,
        state=state,
    )


def test_parse_and_caption_human_gate() -> None:
    gate = HumanGate(
        kind=HumanGateKind.MISSION_CONFIRM,
        label="确认任务使命",
        prompt="请确认或修正 Mission 后再继续。",
        page_key="project-mission",
    )
    run = _run_with_gate(gate=gate)
    parsed = parse_human_gate(run.state)
    assert parsed is not None
    assert parsed.kind == HumanGateKind.MISSION_CONFIRM
    caption = human_gate_caption(parsed)
    assert caption is not None
    assert "确认任务使命" in caption
    assert "Mission" in caption or "确认" in caption


def test_should_show_compact_when_gate_present() -> None:
    gate = HumanGate(
        kind=HumanGateKind.CONCEPT_SELECTION,
        label="选定概念方向",
        prompt="请选择一个概念方向后再继续。",
        page_key="concept-exploration",
    )
    run = _run_with_gate(gate=gate)
    assert should_show_compact_gate(run) is True


def test_should_show_compact_when_awaiting_without_gate_payload() -> None:
    run = _run_with_gate(gate=None)
    assert should_show_compact_gate(run) is True


def test_should_hide_compact_when_running_without_gate() -> None:
    run = _run_with_gate(
        gate=None,
        stage_status=OrchestrationStageStatus.RUNNING,
    )
    assert should_show_compact_gate(run) is False


def test_parse_human_gate_ignores_junk() -> None:
    assert parse_human_gate(None) is None
    assert parse_human_gate({}) is None
    assert parse_human_gate({"human_gate": "nope"}) is None
    assert human_gate_caption(None) is None
