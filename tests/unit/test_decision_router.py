"""Tests for Decision Router / HumanGate / DesignReflection."""

from __future__ import annotations

from uuid import uuid4

from archium.application.design_reflection import (
    reflection_from_context,
    reflection_from_critique,
)
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.design_critique import (
    DesignCritiqueItem,
    DesignCritiqueReport,
    DesignCritiqueVerdict,
)
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType
from archium.domain.orchestration import (
    HumanGateKind,
    OrchestrationPlanSource,
    OrchestrationStage,
    OrchestrationStageStatus,
    build_orchestration_plan,
    human_gate_for_stage,
    replan_from_context,
)


def test_replan_inserts_research_after_explore_completed() -> None:
    plan = build_orchestration_plan(
        uuid4(),
        workflow=RecommendedWorkflow.EXPLORE,
    )
    plan.stages[0].status = OrchestrationStageStatus.COMPLETED  # explore
    plan.active_index = 0

    ctx = ProjectContext.compose(
        knowledge_state=KnowledgeState(
            completeness_score=0.2,
            unknown=["气候数据", "规范约束"],
            recommended_workflow=RecommendedWorkflow.RESEARCH.value,
        ),
        next_actions=[
            NextBestAction(
                action=NextBestActionType.RESEARCH,
                reason="知识不足，先研究",
                priority=0,
            )
        ],
        understanding_summary="一句话概念，证据不足",
    )
    # Force recommended workflow on context
    ctx = ctx.model_copy(update={"recommended_workflow": RecommendedWorkflow.RESEARCH})

    updated, decision = replan_from_context(plan, context=ctx)
    assert decision.changed
    assert updated.source == OrchestrationPlanSource.CONTEXT_REPLAN
    stages = [s.stage for s in updated.stages]
    assert stages[0] == OrchestrationStage.EXPLORE
    assert OrchestrationStage.RESEARCH in stages
    assert updated.stages[0].status == OrchestrationStageStatus.COMPLETED
    # pending should start with research
    pending = [s.stage for s in updated.stages if s.status == OrchestrationStageStatus.PENDING]
    assert pending[0] == OrchestrationStage.RESEARCH


def test_replan_keeps_inflight_mission_gate() -> None:
    plan = build_orchestration_plan(
        uuid4(),
        workflow=RecommendedWorkflow.EXPLORE,
    )
    plan.stages[0].status = OrchestrationStageStatus.COMPLETED
    plan.stages[1].status = OrchestrationStageStatus.AWAITING_USER  # mission
    plan.active_index = 1

    ctx = ProjectContext.compose(
        knowledge_state=KnowledgeState(completeness_score=0.8),
        next_actions=[],
        understanding_summary="可直接交付",
    )
    ctx = ctx.model_copy(update={"recommended_workflow": RecommendedWorkflow.DELIVER})

    updated, decision = replan_from_context(plan, context=ctx)
    assert decision.changed
    assert updated.stages[1].stage == OrchestrationStage.MISSION_PLANNING
    assert updated.stages[1].status == OrchestrationStageStatus.AWAITING_USER
    pending = [s.stage for s in updated.stages if s.status == OrchestrationStageStatus.PENDING]
    assert OrchestrationStage.PRESENTATION in pending
    assert OrchestrationStage.MISSION_PLANNING not in pending


def test_replan_noop_when_tail_unchanged() -> None:
    plan = build_orchestration_plan(
        uuid4(),
        workflow=RecommendedWorkflow.MISSION,
    )
    ctx = ProjectContext.compose(
        knowledge_state=KnowledgeState(),
        next_actions=[],
    )
    ctx = ctx.model_copy(update={"recommended_workflow": RecommendedWorkflow.MISSION})
    updated, decision = replan_from_context(plan, context=ctx)
    assert not decision.changed
    assert updated is plan or [
        s.stage for s in updated.stages
    ] == [s.stage for s in plan.stages]


def test_human_gate_for_explore() -> None:
    gate = human_gate_for_stage(OrchestrationStage.EXPLORE, page_key="concept-exploration")
    assert gate.kind == HumanGateKind.CONCEPT_SELECTION
    assert "方向" in gate.label
    assert gate.review_gate == "orchestration:explore"


def test_human_gate_workstream_is_strategy_confirm() -> None:
    gate = human_gate_for_stage(OrchestrationStage.WORKSTREAM_EXECUTION)
    assert gate.kind == HumanGateKind.STRATEGY_CONFIRM


def test_reflection_from_context_and_critique() -> None:
    ctx = ProjectContext.compose(
        knowledge_state=KnowledgeState(
            unknown=["场地坡度"],
            missing_information=["消防疏散"],
        ),
        next_actions=[
            NextBestAction(
                action=NextBestActionType.RESEARCH,
                reason="补场地研究",
                priority=0,
            )
        ],
        understanding_summary="山地艺术中心概念阶段",
        input_sources=[],
    )
    # compose may set assumptions from state
    reflection = reflection_from_context(
        ctx.model_copy(update={"assumptions": ["体量应弱化"]})
    )
    assert not reflection.is_empty()
    assert "山地" in reflection.why or reflection.unverified_assumptions

    report = DesignCritiqueReport(
        verdict=DesignCritiqueVerdict.CAUTION,
        summary="证据链偏弱",
        weaknesses=[
            DesignCritiqueItem(text="公私分区未论证"),
        ],
        missing_evidence=[
            DesignCritiqueItem(text="缺少场地剖面依据"),
        ],
        form_only_risk=True,
    )
    from_critique = reflection_from_critique(report)
    assert from_critique.source == "critique"
    assert any("形式" in r for r in from_critique.top_risks)
