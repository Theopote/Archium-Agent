"""Unit tests for multi-axis KnowledgeDimensions / Knowledge Vector."""

from __future__ import annotations

from unittest.mock import MagicMock

from archium.application.context.knowledge_assessor import KnowledgeAssessor
from archium.application.context.knowledge_dimensions_builder import (
    dimensions_from_rule_signals,
)
from archium.application.context.knowledge_vector_policy import (
    actions_from_knowledge_vector,
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
from archium.domain.intent.knowledge_dimensions import (
    KnowledgeDimensions,
    KnowledgeVector,
)
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState
from archium.domain.intent.next_best_action import NextBestActionType


def test_knowledge_vector_is_dimensions_alias() -> None:
    assert KnowledgeVector is KnowledgeDimensions


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
    assert dims.facts == dims.information_completeness
    assert "design_readiness" in dims.as_vector()

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


def test_vector_policy_constraint_low_asks() -> None:
    dims = KnowledgeDimensions(
        information_completeness=0.5,
        design_intent_clarity=0.7,
        evidence_confidence=0.5,
        constraint_understanding=0.2,
        user_alignment=0.5,
        research_need=0.4,
    )
    actions = actions_from_knowledge_vector(dims)
    assert actions[0].action == NextBestActionType.ASK
    assert "约束" in actions[0].reason


def test_vector_policy_evidence_low_verifies() -> None:
    dims = KnowledgeDimensions(
        information_completeness=0.6,
        design_intent_clarity=0.65,
        evidence_confidence=0.2,
        constraint_understanding=0.55,
        user_alignment=0.5,
        research_need=0.3,
    )
    actions = actions_from_knowledge_vector(dims)
    assert actions[0].action == NextBestActionType.ASK
    assert "证据" in actions[0].reason or "核实" in actions[0].reason


def test_vector_policy_design_ready_advances() -> None:
    dims = KnowledgeDimensions(
        information_completeness=0.75,
        design_intent_clarity=0.8,
        evidence_confidence=0.7,
        constraint_understanding=0.7,
        user_alignment=0.7,
        research_need=0.2,
    )
    assert float(dims.design_readiness) >= 0.65
    actions = actions_from_knowledge_vector(dims)
    assert actions[0].action == NextBestActionType.GENERATE_MISSION


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
    assert "%" not in display.headline
    assert "意图清晰" in display.headline or "阶段" in display.headline
    assert display.vector_bars  # metrics still available for diagnostics
    assert "完整度约" not in display.headline
    assert display.partner_headline


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


def test_knowledge_state_roundtrip_keeps_dimensions() -> None:
    state = KnowledgeState(
        dimensions=KnowledgeDimensions(
            information_completeness=0.3,
            design_intent_clarity=0.8,
            evidence_confidence=0.2,
            constraint_understanding=0.25,
            user_alignment=0.5,
            research_need=0.7,
        )
    ).with_synced_legacy_scores()
    restored = KnowledgeState.model_validate(state.model_dump(mode="json"))
    assert restored.dimensions.design_intent_clarity == 0.8
    assert restored.dimensions.design_readiness >= 0.0
