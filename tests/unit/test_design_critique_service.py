"""Unit tests for Architectural Design Critic (concept challenge)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from archium.application.review.design_critique_service import DesignCritiqueService
from archium.config.settings import Settings
from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_critique import DesignCritiqueVerdict
from archium.domain.design_rationale import DesignRationale
from archium.domain.intent.design_intent import DesignIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.llm.design_critique_schemas import (
    DesignCritiqueDraft,
    DesignCritiqueItemDraft,
)


def _formal_direction() -> ConceptDirection:
    return ConceptDirection(
        id=uuid4(),
        project_id=uuid4(),
        title="雕塑感体量",
        summary="强调立面韵律与材质表情的雕塑感造型",
        formal_language="几何体量与立面韵律",
        spatial_strategy="形式主导的轴线编排",
        design_rationale=DesignRationale(
            statement="以形式语言塑造场所感",
            reasons=["雕塑感"],
            evidence=[],
            confidence=0.4,
        ),
    )


def test_critique_rules_flag_missing_evidence_and_form_only() -> None:
    llm = MagicMock()
    llm.generate_structured.side_effect = RuntimeError("llm down")
    service = DesignCritiqueService(MagicMock(), llm, settings=Settings(_env_file=None))
    report = service.critique(
        _formal_direction(),
        design_intent=DesignIntent(theme="形式实验"),
        research_summaries=[],
    )
    assert report.missing_evidence
    assert any("依据" in item.text or "证据" in item.text for item in report.missing_evidence)
    assert report.alternative_directions
    assert report.form_only_risk is True
    assert report.verdict in {
        DesignCritiqueVerdict.CAUTION,
        DesignCritiqueVerdict.REJECT,
    }
    # Critic must not mutate direction fields — service only returns report
    assert report.source in {"rules", "mixed"}


def test_critique_llm_draft_merged_with_rules() -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = DesignCritiqueDraft(
        verdict="proceed",
        summary="模型偏乐观",
        strengths=[
            DesignCritiqueItemDraft(text="轴线清晰", challenge="why", severity="suggestion")
        ],
        weaknesses=[],
        missing_evidence=[],
        alternative_directions=[],
        form_only_risk=False,
    )
    service = DesignCritiqueService(MagicMock(), llm, settings=Settings(_env_file=None))
    direction = ConceptDirection(
        id=uuid4(),
        project_id=uuid4(),
        title="礼仪轴",
        summary="回应礼佛流线问题",
        spatial_strategy="礼仪轴线与场地入口矛盾",
        design_rationale=DesignRationale(
            statement="礼仪优先",
            evidence=[],
            confidence=0.5,
        ),
    )
    report = service.critique(
        direction,
        design_intent=DesignIntent(
            theme="寺庙",
            problem_statement="礼佛流线与后勤冲突",
        ),
        research_summaries=[],
    )
    assert report.strengths
    # Rules must still inject missing evidence when rationale has none
    assert report.missing_evidence
    assert report.verdict != DesignCritiqueVerdict.PROCEED or report.missing_evidence


def test_enforce_block_mode_raises_on_reject() -> None:
    llm = MagicMock()
    llm.generate_structured.side_effect = RuntimeError("llm down")
    settings = Settings(_env_file=None, design_critique_on_select="block")
    service = DesignCritiqueService(MagicMock(), llm, settings=settings)
    with pytest.raises(WorkflowError, match="设计批判阻断"):
        service.enforce_on_select(_formal_direction(), design_intent=DesignIntent())


def test_enforce_warn_mode_never_raises() -> None:
    llm = MagicMock()
    llm.generate_structured.side_effect = RuntimeError("llm down")
    settings = Settings(_env_file=None, design_critique_on_select="warn")
    service = DesignCritiqueService(MagicMock(), llm, settings=settings)
    result = service.enforce_on_select(_formal_direction())
    assert result.blocked is False
    assert result.warnings
    assert result.report.missing_evidence
