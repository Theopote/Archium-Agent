"""Unit tests for multi-axis KnowledgeDimensions."""

from __future__ import annotations

from unittest.mock import MagicMock

from archium.application.context.knowledge_assessor import KnowledgeAssessor
from archium.application.context.knowledge_dimensions_builder import (
    dimensions_from_rule_signals,
)
from archium.application.context.next_action_selector import default_actions_for_dimensions
from archium.application.context_evidence import ProjectEvidencePack
from archium.application.project_knowledge_display import (
    KnowledgeSituation,
    build_project_knowledge_display,
    classify_knowledge_situation,
)
from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.project_context import (
    ProjectContext,
    infer_lifecycle_stage,
    infer_recommended_workflow,
)
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.intent.knowledge_dimensions import KnowledgeDimensions
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState
from archium.domain.intent.next_best_action import NextBestActionType


def test_temple_case_high_intent_low_information() -> None:
    dims = dimensions_from_rule_signals(
        user_text=(
            "秦岭深处一座寺庙改扩建：强调礼佛轴线、庭院序列与禅意氛围，"
            "形式克制，材料以木石为主，空间叙事重于图纸完备。"
        ),
        evidence=ProjectEvidencePack(),
        evidence_ratio=0.05,
    )
    assert dims.design_intent_clarity >= 0.7
    assert dims.information_completeness < 0.35
    assert dims.research_need >= 0.5

    state = KnowledgeState(
        dimensions=dims,
        maturity_stage=KnowledgeMaturityStage.CONCEPT_FORMATION,
    ).with_synced_legacy_scores()
    assert infer_lifecycle_stage(state) == ProjectLifecycleStage.CONCEPT
    assert (
        infer_recommended_workflow(state, []) == RecommendedWorkflow.EXPLORE
    )
    actions = default_actions_for_dimensions(dims)
    assert actions[0].action == NextBestActionType.EXPLORE_DIRECTIONS
    assert classify_knowledge_situation(state) == KnowledgeSituation.INTENT_LED


def test_rich_materials_fuzzy_intent_asks_first() -> None:
    dims = KnowledgeDimensions(
        information_completeness=0.8,
        design_intent_clarity=0.25,
        evidence_confidence=0.7,
        constraint_understanding=0.6,
        user_alignment=0.4,
        research_need=0.3,
    )
    actions = default_actions_for_dimensions(dims)
    assert actions[0].action == NextBestActionType.ASK


def test_legacy_knowledge_state_bridges_dimensions() -> None:
    state = KnowledgeState(
        completeness_score=0.5,
        evidence_ratio=0.4,
        assumption_ratio=0.5,
    )
    dims = state.effective_dimensions()
    assert dims.information_completeness == 0.5
    assert dims.evidence_confidence == 0.4


def test_display_headline_uses_intent_and_information() -> None:
    dims = KnowledgeDimensions(
        information_completeness=0.2,
        design_intent_clarity=0.85,
        evidence_confidence=0.25,
        constraint_understanding=0.3,
        user_alignment=0.6,
        research_need=0.8,
    )
    state = KnowledgeState(
        dimensions=dims,
        maturity_stage=KnowledgeMaturityStage.CONCEPT_FORMATION,
    ).with_synced_legacy_scores()
    ctx = ProjectContext.compose(
        knowledge_state=state,
        next_actions=[],
        understanding_summary="寺庙概念清晰，图纸很少。",
    )
    display = build_project_knowledge_display(ctx)
    assert display.situation == KnowledgeSituation.INTENT_LED
    assert "意图" in display.headline
    assert "资料" in display.headline
    assert "完整度约" not in display.headline


def test_rule_fallback_temple_explore_first() -> None:
    llm = MagicMock()
    llm.generate_structured.side_effect = RuntimeError("down")
    service = KnowledgeAssessor(llm)
    result = service.assess_text(
        "一座山林寺庙：礼佛轴线、禅意庭院与仪式空间是核心意图。",
        project_name="云寺",
        evidence=ProjectEvidencePack(),
    )
    assert result.knowledge_state.dimensions.design_intent_clarity >= 0.55
    assert result.actions[0].action == NextBestActionType.EXPLORE_DIRECTIONS
