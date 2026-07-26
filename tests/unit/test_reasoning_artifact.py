"""Unit tests for ReasoningArtifact identity (Phase R2)."""

from __future__ import annotations

from uuid import uuid4

from archium.application.reasoning_artifact import (
    build_reasoning_artifact_from_direction,
    ensure_direction_reasoning,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_rationale import DesignRationale
from archium.domain.enums import ConceptDirectionStatus
from archium.domain.reasoning_artifact import (
    dump_reasoning_storage,
    parse_reasoning_storage,
)


def _direction(**kwargs) -> ConceptDirection:
    defaults = {
        "project_id": uuid4(),
        "title": "嵌入地景",
        "summary": "减少山地切割",
        "spatial_strategy": "低体量嵌入",
        "reference_case_ids": ["therme_vals"],
        "status": ConceptDirectionStatus.DRAFT,
        "design_rationale": DesignRationale(
            statement="嵌入式布局",
            observation="基地位于山地",
            problem="减少人工切割",
            hypothesis="建筑应成为地景一部分",
            strategy="低体量嵌入式布局",
            evidence=["case:therme_vals"],
            confidence=0.7,
        ),
    }
    defaults.update(kwargs)
    return ConceptDirection(**defaults)


def test_ensure_direction_reasoning_binds_case_refs() -> None:
    direction = ensure_direction_reasoning(_direction())
    assert direction.reasoning is not None
    assert direction.reasoning.project_id == direction.project_id
    assert direction.reasoning.source_direction_id == direction.id
    assert "therme_vals" in direction.reasoning.evidence_refs.case_ids
    assert direction.reasoning.is_proceedable()
    assert direction.design_rationale is not None
    assert direction.design_rationale.is_proceedable_chain()


def test_ensure_preserves_reasoning_id() -> None:
    first = ensure_direction_reasoning(_direction())
    assert first.reasoning is not None
    rid = first.reasoning.id
    second = ensure_direction_reasoning(first)
    assert second.reasoning is not None
    assert second.reasoning.id == rid


def test_parse_legacy_flat_and_envelope_roundtrip() -> None:
    project_id = uuid4()
    direction_id = uuid4()
    flat = DesignRationale(
        statement="主张",
        hypothesis="假设",
        strategy="策略",
    ).model_dump(mode="json")
    rationale, artifact = parse_reasoning_storage(
        flat,
        project_id=project_id,
        direction_id=direction_id,
    )
    assert rationale is not None
    assert artifact is not None
    assert artifact.rationale.strategy == "策略"

    direction = _direction(id=direction_id, project_id=project_id)
    direction = ensure_direction_reasoning(direction)
    payload = dump_reasoning_storage(
        reasoning=direction.reasoning,
        design_rationale=direction.design_rationale,
    )
    assert payload is not None
    assert payload.get("_kind") == "reasoning_artifact"
    again_r, again_a = parse_reasoning_storage(
        payload,
        project_id=project_id,
        direction_id=direction_id,
    )
    assert again_r is not None and again_a is not None
    assert again_a.id == direction.reasoning.id
    assert again_a.evidence_refs.case_ids


def test_spawn_revision_lineage() -> None:
    from archium.domain.design_rationale import DesignRationale
    from archium.domain.reasoning_artifact import ReasoningArtifact

    parent = ReasoningArtifact(
        project_id=uuid4(),
        rationale=DesignRationale(statement="v1", hypothesis="h", strategy="s"),
        revision=1,
    )
    child = parent.spawn_revision(
        rationale=DesignRationale(statement="v2", hypothesis="h2", strategy="s2"),
        critique_verdict="caution",
        critique_summary="补丁后",
    )
    assert child.revision == 2
    assert child.parent_reasoning_id == parent.id
    assert child.id != parent.id
    assert child.verified is False
    assert child.last_critique_verdict == "caution"
    assert "v2" in child.lineage_dict()["reasoning_id"] or child.lineage_dict()[
        "revision"
    ] == 2

    artifact = build_reasoning_artifact_from_direction(_direction())
    assert artifact is not None
    assert "嵌入" in artifact.to_prompt_block() or "地景" in artifact.to_prompt_block()
