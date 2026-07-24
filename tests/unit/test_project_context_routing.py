"""Tests for ProjectContext → legacy origin_mode routing policy."""

from __future__ import annotations

from archium.domain.context.legacy_origin import infer_legacy_origin_mode
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.enums import ProjectOriginMode
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType


def _ctx(
    *,
    knowledge_state: KnowledgeState | None = None,
    suggested_origin: ProjectOriginMode = ProjectOriginMode.EXISTING_PROJECT,
    workflow: RecommendedWorkflow | None = None,
) -> ProjectContext:
    ks = knowledge_state or KnowledgeState(
        completeness_score=0.32,
        maturity_stage=KnowledgeMaturityStage.DESIGN_ANALYSIS,
        evidence_ratio=0.2,
    )
    actions = [
        NextBestAction(action=NextBestActionType.ASK, reason="澄清", priority=0)
    ]
    ctx = ProjectContext.compose(
        knowledge_state=ks,
        next_actions=actions,
        suggested_origin_mode=suggested_origin,
    )
    if workflow is not None:
        ctx = ctx.model_copy(update={"recommended_workflow": workflow})
    return ctx


def test_partial_knowledge_maps_to_concept_exploration() -> None:
    legacy = infer_legacy_origin_mode(_ctx())
    assert legacy == ProjectOriginMode.CONCEPT_EXPLORATION


def test_rich_materials_maps_to_existing_project() -> None:
    legacy = infer_legacy_origin_mode(
        _ctx(
            knowledge_state=KnowledgeState(
                completeness_score=0.72,
                maturity_stage=KnowledgeMaturityStage.TECHNICAL_PRESENTATION,
                evidence_ratio=0.65,
            ),
            workflow=RecommendedWorkflow.MATERIALS,
        )
    )
    assert legacy == ProjectOriginMode.EXISTING_PROJECT


def test_programming_signal_maps_to_research_programming() -> None:
    legacy = infer_legacy_origin_mode(
        _ctx(
            suggested_origin=ProjectOriginMode.RESEARCH_PROGRAMMING,
            workflow=RecommendedWorkflow.RESEARCH,
        )
    )
    assert legacy == ProjectOriginMode.RESEARCH_PROGRAMMING
