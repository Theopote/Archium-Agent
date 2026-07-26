"""Unit tests for Phase L1 design loop: Critique → Revise → Re-Critique."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from archium.application.design_loop import run_design_loop_on_select
from archium.application.review.design_critique_service import (
    DesignCritiqueGateResult,
    DesignCritiqueService,
)
from archium.config.settings import Settings
from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_critique import (
    DesignCritiqueChallenge,
    DesignCritiqueItem,
    DesignCritiqueReport,
    DesignCritiqueVerdict,
)
from archium.domain.design_rationale import DesignRationale
from archium.domain.enums import ConceptDirectionStatus
from archium.domain.intent.design_intent import DesignIntent
from archium.exceptions import WorkflowError


def _direction(**kwargs) -> ConceptDirection:
    defaults = {
        "id": uuid4(),
        "project_id": uuid4(),
        "title": "嵌入地景",
        "summary": "减少山地切割",
        "spatial_strategy": "低体量嵌入式布局",
        "formal_language": "克制体量",
        "status": ConceptDirectionStatus.DRAFT,
        "design_rationale": DesignRationale(
            statement="嵌入式布局",
            evidence=["现场：坡度明显"],
            confidence=0.5,
        ),
    }
    defaults.update(kwargs)
    return ConceptDirection(**defaults)


def _gate(
    report: DesignCritiqueReport,
    *,
    mode: str = "warn",
) -> DesignCritiqueGateResult:
    return DesignCritiqueGateResult(
        report=report,
        mode=mode,
        warnings=report.display_warnings(),
    )


def test_no_revise_on_proceed_marks_verified() -> None:
    direction = _direction(
        design_rationale=DesignRationale(
            statement="嵌入",
            observation="山地",
            problem="切割",
            hypothesis="应嵌入地景",
            strategy="低体量嵌入",
            evidence=["踏勘"],
            confidence=0.8,
        )
    )
    report = DesignCritiqueReport(
        direction_id=direction.id,
        project_id=direction.project_id,
        verdict=DesignCritiqueVerdict.PROCEED,
        summary="可继续",
        source="rules",
    )
    critic = DesignCritiqueService(
        MagicMock(), MagicMock(), settings=Settings(_env_file=None)
    )
    result = run_design_loop_on_select(
        direction,
        _gate(report),
        critic=critic,
    )
    assert result.revised is False
    assert result.recritique is None
    assert result.direction.reasoning is not None
    assert result.direction.reasoning.verified is True
    assert any("verified" in n for n in result.notes)


def test_revise_triggers_recritique_and_verified_only_on_proceed() -> None:
    direction = _direction()
    first = DesignCritiqueReport(
        direction_id=direction.id,
        project_id=direction.project_id,
        verdict=DesignCritiqueVerdict.CAUTION,
        summary="链不完整",
        chain_incomplete=True,
        weaknesses=[
            DesignCritiqueItem(
                text="缺假设与策略",
                challenge=DesignCritiqueChallenge.CHAIN,
                severity="high",
            )
        ],
        missing_evidence=[],
        source="rules",
    )
    llm = MagicMock()
    llm.generate_structured.side_effect = RuntimeError("should not call on rules_only")
    critic = DesignCritiqueService(
        MagicMock(), llm, settings=Settings(_env_file=None)
    )
    result = run_design_loop_on_select(
        direction,
        _gate(first),
        critic=critic,
        design_intent=DesignIntent(
            theme="山地",
            problem_statement="减少山地切割",
        ),
        research_summaries=["坡地研究摘要"],
        recritique_rules_only=True,
    )
    assert result.revised is True
    assert result.recritique is not None
    assert result.gate is result.recritique
    assert result.direction.design_rationale is not None
    assert result.direction.design_rationale.is_proceedable_chain()
    # After chain fill + evidence/research, rules may proceed or caution —
    # verified only if re-critique proceed.
    if result.gate.report.verdict == DesignCritiqueVerdict.PROCEED:
        assert result.direction.reasoning is not None
        assert result.direction.reasoning.verified is True
    else:
        assert (
            result.direction.reasoning is None
            or result.direction.reasoning.verified is False
        )
    assert any("修订后再批判" in n for n in result.notes)
    llm.generate_structured.assert_not_called()


def test_revise_does_not_soft_verify_without_proceed() -> None:
    """Even after chain fill, caution re-critique must not set verified."""
    direction = _direction(
        design_rationale=DesignRationale(
            statement="形式主张",
            evidence=[],
            confidence=0.3,
        ),
        formal_language="雕塑感立面韵律与材质表情",
        spatial_strategy="形式主导轴线",
        summary="强调立面韵律与材质表情的雕塑感造型",
    )
    first = DesignCritiqueReport(
        direction_id=direction.id,
        project_id=direction.project_id,
        verdict=DesignCritiqueVerdict.REJECT,
        summary="形式空转",
        chain_incomplete=True,
        form_only_risk=True,
        source="rules",
    )
    critic = DesignCritiqueService(
        MagicMock(),
        MagicMock(),
        settings=Settings(_env_file=None),
    )
    result = run_design_loop_on_select(
        direction,
        _gate(first),
        critic=critic,
        research_summaries=[],
        recritique_rules_only=True,
    )
    assert result.revised is True
    assert result.gate.report.verdict != DesignCritiqueVerdict.PROCEED
    assert result.direction.reasoning is None or (
        result.direction.reasoning.verified is False
    )


def test_recritique_block_mode_raises() -> None:
    direction = _direction()
    first = DesignCritiqueReport(
        direction_id=direction.id,
        project_id=direction.project_id,
        verdict=DesignCritiqueVerdict.CAUTION,
        chain_incomplete=True,
        summary="需修订",
        source="rules",
    )
    settings = Settings(_env_file=None, design_critique_on_select="block")
    critic = DesignCritiqueService(MagicMock(), MagicMock(), settings=settings)

    def _reject_recritique(*_a, **_k):
        report = DesignCritiqueReport(
            direction_id=direction.id,
            project_id=direction.project_id,
            verdict=DesignCritiqueVerdict.REJECT,
            summary="修订后仍不宜固化",
            chain_incomplete=True,
            source="rules",
        )
        return critic.apply_select_gate(report, mode="block")

    critic.enforce_on_select = _reject_recritique  # type: ignore[method-assign]
    with pytest.raises(WorkflowError, match="设计批判阻断"):
        run_design_loop_on_select(
            direction,
            _gate(first, mode="block"),
            critic=critic,
            research_summaries=[],
            recritique_rules_only=True,
        )
