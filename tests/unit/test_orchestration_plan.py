"""Unit tests for OrchestrationPlan mapping."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType
from archium.domain.orchestration import (
    OrchestrationPlanSource,
    OrchestrationStage,
    build_orchestration_plan,
    stage_hint_for_action,
    stages_for_recommended_workflow,
)


def test_stages_for_each_recommended_workflow() -> None:
    assert OrchestrationStage.EXPLORE in stages_for_recommended_workflow(
        RecommendedWorkflow.EXPLORE
    )
    assert OrchestrationStage.MATERIALS in stages_for_recommended_workflow(
        RecommendedWorkflow.MATERIALS
    )
    assert OrchestrationStage.MISSION_PLANNING in stages_for_recommended_workflow(
        RecommendedWorkflow.MISSION
    )
    deliver = stages_for_recommended_workflow(RecommendedWorkflow.DELIVER)
    assert deliver[0] == OrchestrationStage.PRESENTATION
    assert OrchestrationStage.DELIVER in deliver


def test_build_plan_from_workflow() -> None:
    project_id = uuid4()
    plan = build_orchestration_plan(
        project_id,
        workflow=RecommendedWorkflow.EXPLORE,
    )
    assert plan.project_id == project_id
    assert plan.source == OrchestrationPlanSource.RECOMMENDED_WORKFLOW
    assert plan.stages[0].stage == OrchestrationStage.EXPLORE
    assert plan.stages[0].page_key == "concept-exploration"
    assert plan.active_stage() is not None


def test_build_plan_from_context_uses_nba_source() -> None:
    ctx = ProjectContext.compose(
        knowledge_state=KnowledgeState(completeness_score=0.3),
        next_actions=[
            NextBestAction(
                action=NextBestActionType.GENERATE_MISSION,
                reason="理解任务",
                priority=0,
            )
        ],
        understanding_summary="部分资料",
    )
    plan = build_orchestration_plan(uuid4(), context=ctx)
    assert plan.source == OrchestrationPlanSource.NBA
    assert plan.stages
    assert any(s.stage == OrchestrationStage.MISSION_PLANNING for s in plan.stages)


def test_stage_hint_rotates_plan() -> None:
    plan = build_orchestration_plan(
        uuid4(),
        workflow=RecommendedWorkflow.EXPLORE,
        stage_hint=OrchestrationStage.MISSION_PLANNING,
    )
    assert plan.stages[0].stage == OrchestrationStage.MISSION_PLANNING


def test_stage_hint_for_action() -> None:
    assert stage_hint_for_action(NextBestActionType.RESEARCH) == OrchestrationStage.RESEARCH
    assert (
        stage_hint_for_action(NextBestActionType.GENERATE_MISSION)
        == OrchestrationStage.MISSION_PLANNING
    )
