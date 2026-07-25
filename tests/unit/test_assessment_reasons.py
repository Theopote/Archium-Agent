"""Unit tests for ContextAssessmentReason / reasoning trace."""

from __future__ import annotations

from unittest.mock import MagicMock

from archium.application.context.assessment_reason_builder import (
    synthesize_assessment_reasons,
)
from archium.application.context.knowledge_assessor import KnowledgeAssessor
from archium.application.context.knowledge_dimensions_builder import (
    dimensions_from_rule_signals,
)
from archium.application.context.next_action_selector import default_actions_for_dimensions
from archium.application.context_evidence import ProjectEvidencePack
from archium.domain.intent.context_assessment_reason import (
    AssessmentReasonAxis,
    AssessmentReasonPolarity,
    ContextAssessmentReason,
)
from archium.domain.intent.knowledge_dimensions import KnowledgeDimensions
from archium.domain.intent.next_best_action import NextBestActionType


_TEMPLE_TEXT = (
    "秦岭深处一座寺庙改扩建：强调礼佛轴线、庭院序列与禅意氛围，"
    "形式克制，材料以木石为主，空间叙事重于图纸完备。"
)


def test_temple_case_reasons_include_intent_and_sparse_materials() -> None:
    dims = dimensions_from_rule_signals(
        user_text=_TEMPLE_TEXT,
        evidence=ProjectEvidencePack(),
        evidence_ratio=0.05,
    )
    actions = default_actions_for_dimensions(dims)
    reasons = synthesize_assessment_reasons(
        dimensions=dims,
        known={"type": "寺庙", "location": "秦岭"},
        unknown=["场地测绘", "建筑面积"],
        actions=actions,
        evidence=ProjectEvidencePack(),
    )
    factors = " ".join(r.factor for r in reasons)
    assert "意图" in factors
    assert "资料" in factors or "缺少" in factors
    assert any(r.related_axis == AssessmentReasonAxis.INTENT for r in reasons)
    assert any(r.polarity == AssessmentReasonPolarity.BLOCK for r in reasons)
    assert any(r.related_axis == AssessmentReasonAxis.WORKFLOW for r in reasons)
    assert actions[0].action == NextBestActionType.EXPLORE_DIRECTIONS


def test_rule_fallback_attaches_reasons_to_assessment_and_state() -> None:
    assessor = KnowledgeAssessor(MagicMock())
    assessment = assessor._rule_fallback(
        _TEMPLE_TEXT,
        project_name="秦岭寺庙",
        evidence=ProjectEvidencePack(),
    )
    assert assessment.reasons
    assert assessment.knowledge_state.assessment_reasons
    assert assessment.reasons == assessment.knowledge_state.assessment_reasons
    factors = " ".join(r.factor for r in assessment.reasons)
    assert "意图" in factors or "概念" in factors
    assert "资料" in factors or "缺少" in factors


def test_llm_reasons_merged_ahead_of_synthetic() -> None:
    dims = KnowledgeDimensions(
        information_completeness=0.2,
        design_intent_clarity=0.8,
        evidence_confidence=0.1,
        constraint_understanding=0.2,
        user_alignment=0.6,
        research_need=0.7,
    )
    llm = [
        ContextAssessmentReason(
            factor="礼制轴线意图明确",
            evidence="用户强调轴线与庭院序列",
            impact="可直接进入概念探索",
            confidence=0.92,
            polarity=AssessmentReasonPolarity.SUPPORT,
            related_axis=AssessmentReasonAxis.INTENT,
        )
    ]
    reasons = synthesize_assessment_reasons(
        dimensions=dims,
        actions=default_actions_for_dimensions(dims),
        llm_reasons=llm,
    )
    assert reasons[0].factor == "礼制轴线意图明确"
    assert len(reasons) >= 2
