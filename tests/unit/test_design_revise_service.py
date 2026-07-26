"""Unit tests for Critic→Revise (Phase R3)."""

from __future__ import annotations

from uuid import uuid4

from archium.application.design_reflection import reflection_from_critique
from archium.application.design_revise_service import (
    apply_reflection_adjustments,
    revise_direction_from_critique,
    should_revise_from_critique,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_critique import (
    DesignCritiqueChallenge,
    DesignCritiqueItem,
    DesignCritiqueReport,
    DesignCritiqueVerdict,
)
from archium.domain.design_rationale import DesignRationale
from archium.domain.enums import ConceptDirectionStatus


def _direction(**kwargs) -> ConceptDirection:
    defaults = {
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
            # incomplete chain on purpose
        ),
    }
    defaults.update(kwargs)
    return ConceptDirection(**defaults)


def test_should_revise_when_chain_incomplete() -> None:
    report = DesignCritiqueReport(
        verdict=DesignCritiqueVerdict.CAUTION,
        chain_incomplete=True,
        summary="链不完整",
    )
    assert should_revise_from_critique(report) is True


def test_revise_fills_chain_and_applies_risks() -> None:
    direction = _direction()
    report = DesignCritiqueReport(
        direction_id=direction.id,
        project_id=direction.project_id,
        verdict=DesignCritiqueVerdict.CAUTION,
        summary="缺策略假设",
        chain_incomplete=True,
        form_only_risk=False,
        weaknesses=[
            DesignCritiqueItem(
                text="缺少可核验场地剖面",
                challenge=DesignCritiqueChallenge.EVIDENCE,
                severity="high",
            )
        ],
        missing_evidence=[
            DesignCritiqueItem(
                text="无坡度实测",
                challenge=DesignCritiqueChallenge.EVIDENCE,
                severity="medium",
            )
        ],
        alternative_directions=[
            DesignCritiqueItem(
                text="可先定等高台地策略再定形式",
                challenge=DesignCritiqueChallenge.ALTERNATIVE,
                severity="suggestion",
            )
        ],
        source="rules",
    )
    result = revise_direction_from_critique(direction, report)
    assert result.changed is True
    assert result.direction.design_rationale is not None
    assert result.direction.design_rationale.is_proceedable_chain()
    assert result.direction.reasoning is not None
    assert any(a.startswith("chain:") for a in result.applied)
    assert any("坡度" in q or "证据" in q for q in result.direction.open_questions) or any(
        "剖面" in r for r in result.direction.risks
    )
    assert result.reflection is not None
    assert result.reflection.next_adjustments


def test_apply_reflection_adjustments_executes_next_adjustments() -> None:
    direction = _direction(
        design_rationale=DesignRationale(
            statement="主张",
            hypothesis="假设已有",
            strategy="策略已有",
            evidence=["a"],
        )
    )
    report = DesignCritiqueReport(
        verdict=DesignCritiqueVerdict.CAUTION,
        summary="需补证",
        missing_evidence=[
            DesignCritiqueItem(
                text="缺规范校核",
                challenge=DesignCritiqueChallenge.EVIDENCE,
                severity="high",
            )
        ],
    )
    reflection = reflection_from_critique(report)
    result = apply_reflection_adjustments(direction, reflection)
    assert result.reflection is not None
    assert result.reflection.next_adjustments
    # Adjustments land in open_questions / risks
    blob = " ".join(result.direction.open_questions + result.direction.risks)
    assert blob.strip()


def test_revise_bumps_reasoning_revision_lineage() -> None:
    from archium.application.reasoning_artifact import ensure_direction_reasoning

    direction = _direction(
        design_rationale=DesignRationale(
            statement="嵌入式布局",
            observation="山地",
            problem="切割",
            hypothesis="应嵌入",
            strategy="低体量",
            evidence=["现场"],
            confidence=0.6,
        )
    )
    direction = ensure_direction_reasoning(direction)
    assert direction.reasoning is not None
    parent_id = direction.reasoning.id
    assert direction.reasoning.revision == 1

    report = DesignCritiqueReport(
        direction_id=direction.id,
        project_id=direction.project_id,
        verdict=DesignCritiqueVerdict.CAUTION,
        summary="需补风险",
        chain_incomplete=False,
        weaknesses=[
            DesignCritiqueItem(
                text="施工分期边界不清",
                challenge=DesignCritiqueChallenge.EVIDENCE,
                severity="high",
            )
        ],
        source="rules",
    )
    result = revise_direction_from_critique(direction, report)
    assert result.changed is True
    assert result.direction.reasoning is not None
    assert result.direction.reasoning.revision == 2
    assert result.direction.reasoning.parent_reasoning_id == parent_id
    assert result.direction.reasoning.id != parent_id
    assert result.direction.reasoning.verified is False
    assert any(a.startswith("lineage:v") for a in result.applied)
    lineage = result.as_dict()["reasoning_lineage"]
    assert isinstance(lineage, dict)
    assert lineage["revision"] == 2

    report = DesignCritiqueReport(
        verdict=DesignCritiqueVerdict.CAUTION,
        chain_incomplete=True,
        summary="链缺口",
    )
    reflection = reflection_from_critique(report)
    assert any("hypothesis" in item or "strategy" in item for item in reflection.next_adjustments)
