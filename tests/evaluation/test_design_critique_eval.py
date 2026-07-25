"""Evaluation: Critic must challenge concepts with counterexamples."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from archium.application.review.design_critique_service import DesignCritiqueService
from archium.config.settings import Settings
from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_rationale import DesignRationale
from archium.domain.intent.design_intent import DesignIntent
from archium.infrastructure.llm.design_critique_schemas import (
    DesignCritiqueDraft,
    DesignCritiqueItemDraft,
)
from tests.evaluation.assertions import assert_critique_offers_counterexamples


def _formal_direction() -> ConceptDirection:
    return ConceptDirection(
        id=uuid4(),
        project_id=uuid4(),
        title="雕塑感体量",
        summary="强调立面韵律与材质表情",
        formal_language="几何体量与立面韵律",
        spatial_strategy="形式主导的轴线编排",
        design_rationale=DesignRationale(
            statement="以形式语言塑造场所感",
            reasons=["雕塑感"],
            evidence=[],
            confidence=0.4,
        ),
        risks=["可建性未知"],
    )


def test_critic_eval_rules_inject_counterexamples_when_llm_empty() -> None:
    """Eval: even empty LLM alternatives must yield counterexamples (rules)."""
    llm = MagicMock()
    llm.generate_structured.return_value = DesignCritiqueDraft(
        verdict="caution",
        summary="形式偏重",
        strengths=[],
        weaknesses=[],
        missing_evidence=[],
        alternative_directions=[],  # Critic must not leave this empty after merge
        form_only_risk=True,
    )
    report = DesignCritiqueService(
        MagicMock(),
        llm,
        settings=Settings(_env_file=None),
    ).critique(
        _formal_direction(),
        design_intent=DesignIntent(theme="形式实验"),
        research_summaries=[],
    )
    assert_critique_offers_counterexamples(report)
    assert report.missing_evidence, "evaluation: Critic should flag missing evidence"


def test_critic_eval_llm_counterexamples_preserved() -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = DesignCritiqueDraft(
        verdict="caution",
        summary="建议比较替代路径",
        strengths=[
            DesignCritiqueItemDraft(text="轴线清晰", challenge="why"),
        ],
        weaknesses=[
            DesignCritiqueItemDraft(
                text="问题陈述弱",
                challenge="problem_fit",
                severity="high",
            )
        ],
        missing_evidence=[
            DesignCritiqueItemDraft(
                text="无场地调研",
                challenge="evidence",
                severity="high",
            )
        ],
        alternative_directions=[
            DesignCritiqueItemDraft(
                text="先定礼仪流线与后勤分区，再谈立面韵律",
                challenge="alternative",
            )
        ],
        form_only_risk=False,
    )
    report = DesignCritiqueService(
        MagicMock(),
        llm,
        settings=Settings(_env_file=None),
    ).critique(
        ConceptDirection(
            id=uuid4(),
            project_id=uuid4(),
            title="礼仪轴",
            summary="回应礼佛流线",
            spatial_strategy="礼仪轴线",
            formal_language="克制体量",
            design_rationale=DesignRationale(
                statement="礼仪优先",
                evidence=["任务书提及礼仪"],
                confidence=0.6,
            ),
            risks=["后勤干扰"],
        ),
        design_intent=DesignIntent(
            theme="寺庙",
            problem_statement="礼佛流线与后勤冲突",
            social_background="地方礼佛活动需求增长",
        ),
        research_summaries=["地方礼仪空间先例摘要"],
    )
    assert_critique_offers_counterexamples(report)
    assert any("礼仪流线" in item.text for item in report.alternative_directions)
