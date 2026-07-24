"""Unit tests for ProjectContext aggregate and stage inference."""

from __future__ import annotations

from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.project_context import (
    ProjectContext,
    infer_lifecycle_stage,
    infer_recommended_workflow,
)
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.enums import ProjectOriginMode
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType


def test_infer_lifecycle_idea_for_sparse_input() -> None:
    state = KnowledgeState(
        completeness_score=0.18,
        maturity_stage=KnowledgeMaturityStage.CONCEPT_FORMATION,
        evidence_ratio=0.05,
    )
    assert infer_lifecycle_stage(state) == ProjectLifecycleStage.IDEA


def test_infer_lifecycle_research_for_partial_materials() -> None:
    state = KnowledgeState(
        completeness_score=0.42,
        maturity_stage=KnowledgeMaturityStage.DESIGN_ANALYSIS,
        evidence_ratio=0.22,
    )
    assert infer_lifecycle_stage(state) == ProjectLifecycleStage.RESEARCH


def test_infer_workflow_from_top_action() -> None:
    state = KnowledgeState(
        completeness_score=0.35,
        maturity_stage=KnowledgeMaturityStage.DESIGN_ANALYSIS,
        evidence_ratio=0.2,
    )
    actions = [
        NextBestAction(
            action=NextBestActionType.ASK,
            reason="澄清关键条件",
            priority=0,
        )
    ]
    assert infer_recommended_workflow(state, actions) == RecommendedWorkflow.MISSION


def test_compose_partial_knowledge_hospital_case() -> None:
    state = KnowledgeState(
        completeness_score=0.32,
        maturity_stage=KnowledgeMaturityStage.DESIGN_ANALYSIS,
        evidence_ratio=0.2,
        assumption_ratio=0.75,
        known={"location": "西安", "type": "医院改造"},
        unknown=["规模", "历史", "用户"],
        missing_information=["规模", "历史", "用户"],
    )
    actions = [
        NextBestAction(
            action=NextBestActionType.ASK,
            reason="基于有限资料澄清",
            priority=0,
        ),
        NextBestAction(
            action=NextBestActionType.EXPLORE_DIRECTIONS,
            reason="并行推演方向",
            priority=1,
        ),
    ]
    ctx = ProjectContext.compose(
        knowledge_state=state,
        next_actions=actions,
        understanding_summary="老院区改造，资料很少。",
        suggested_origin_mode=ProjectOriginMode.EXISTING_PROJECT,
        input_sources=["user_description", "documents:1"],
        primary_page_key="project-mission",
    )
    assert ctx.lifecycle_stage == ProjectLifecycleStage.RESEARCH
    assert ctx.recommended_workflow == RecommendedWorkflow.MISSION
    assert ctx.primary_page_key == "project-mission"
    assert ctx.assumptions
    assert ctx.confidence < 0.5
