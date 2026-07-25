"""Unit tests for context workflow navigation and NBA dispatch."""

from __future__ import annotations

from archium.application.context.next_action_selector import (
    resolve_action_target,
    resolve_workflow_entry,
)
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType


def _partial_context() -> ProjectContext:
    state = KnowledgeState(
        completeness_score=0.34,
        maturity_stage=KnowledgeMaturityStage.DESIGN_ANALYSIS,
        evidence_ratio=0.22,
        assumption_ratio=0.72,
        known={"location": "西安"},
        unknown=["功能分区"],
        fact_count=2,
        source_count=1,
    )
    return ProjectContext.compose(
        knowledge_state=state,
        next_actions=[
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="甲方尚未说清功能分区",
                question="优先改造哪些科室？",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="在约束内推演方向",
                priority=1,
            ),
        ],
        understanding_summary="部分资料改造。",
        primary_page_key="project-mission",
    )


def test_partial_context_ask_routes_to_mission_clarify() -> None:
    ctx = _partial_context()
    entry = resolve_workflow_entry(ctx)
    assert entry.page_key == "project-mission"
    assert entry.mission_step == 3
    assert entry.workflow == RecommendedWorkflow.MISSION


def test_explore_action_routes_to_concept_exploration() -> None:
    dispatch = resolve_action_target(NextBestActionType.EXPLORE_DIRECTIONS)
    assert dispatch.page_key == "concept-exploration"


def test_workflow_explore_fallback() -> None:
    state = KnowledgeState(completeness_score=0.15, evidence_ratio=0.05)
    ctx = ProjectContext.compose(
        knowledge_state=state,
        next_actions=[],
        primary_page_key="",
    )
    ctx = ctx.model_copy(update={"recommended_workflow": RecommendedWorkflow.EXPLORE})
    entry = resolve_workflow_entry(ctx)
    assert entry.page_key == "concept-exploration"


def test_ask_with_pending_facts_routes_to_materials() -> None:
    dispatch = resolve_action_target(
        NextBestActionType.ASK,
        pending_fact_count=2,
    )
    assert dispatch.page_key == "materials"
    assert dispatch.focus == "pending_facts"


def test_apply_workflow_entry_sets_mission_step() -> None:
    from archium.application.context.workflow_navigation import apply_workflow_entry

    state: dict[str, object] = {}
    apply_workflow_entry(
        state,
        resolve_workflow_entry(_partial_context()),
    )
    assert state.get("mission_step") == 3
    assert state.get("context_workflow_entry")
