"""Build / ensure ReasoningArtifact on ConceptDirection (Phase R2)."""

from __future__ import annotations

from uuid import UUID

from archium.domain.case_ref import case_id_from_ref, normalize_case_id_list
from archium.domain.concept_direction import ConceptDirection
from archium.domain.reasoning_artifact import (
    ReasoningArtifact,
    ReasoningEvidenceRefs,
)


def ensure_direction_reasoning(
    direction: ConceptDirection,
    *,
    knowledge_item_ids: list[UUID] | None = None,
    bump_revision: bool = False,
    critique_verdict: str = "",
    critique_summary: str = "",
) -> ConceptDirection:
    """Attach or refresh ReasoningArtifact; preserve stable id when already set.

    Does not invent a rationale — call design_rationale_fallback first if needed.
    When ``bump_revision`` is True and a prior reasoning node exists, spawn a new
    generation (Phase L3 lineage) instead of overwriting the same id.
    """
    rationale = direction.design_rationale
    if rationale is None or rationale.is_empty():
        if direction.reasoning is None or direction.reasoning.is_empty():
            return direction
        rationale = direction.reasoning.rationale

    refs = _merge_evidence_refs(
        direction,
        knowledge_item_ids=knowledge_item_ids,
        existing=direction.reasoning.evidence_refs if direction.reasoning else None,
    )
    parent = direction.reasoning
    if (
        bump_revision
        and parent is not None
        and not parent.is_empty()
    ):
        artifact = parent.spawn_revision(
            rationale=rationale,
            evidence_refs=refs,
            critique_verdict=critique_verdict,
            critique_summary=critique_summary,
        )
        artifact.source_direction_id = direction.id
    elif parent is not None and not parent.is_empty():
        artifact = parent.model_copy(
            update={
                "project_id": direction.project_id,
                "rationale": rationale,
                "evidence_refs": refs,
                "source_direction_id": direction.id,
            }
        )
        if critique_verdict or critique_summary:
            artifact = artifact.with_critique_meta(
                verdict=critique_verdict,
                summary=critique_summary,
            )
        else:
            artifact.touch()
    else:
        artifact = ReasoningArtifact(
            project_id=direction.project_id,
            rationale=rationale,
            evidence_refs=refs,
            source_direction_id=direction.id,
            last_critique_verdict=(critique_verdict or "").strip()[:40],
            last_critique_summary=(critique_summary or "").strip()[:400],
        )
    return direction.model_copy(
        update={
            "design_rationale": rationale,
            "reasoning": artifact,
        }
    )


def build_reasoning_artifact_from_direction(
    direction: ConceptDirection,
    *,
    knowledge_item_ids: list[UUID] | None = None,
) -> ReasoningArtifact | None:
    """Return a reasoning node for the direction, or None if no rationale."""
    ensured = ensure_direction_reasoning(
        direction,
        knowledge_item_ids=knowledge_item_ids,
    )
    if ensured.reasoning is None or ensured.reasoning.is_empty():
        return None
    return ensured.reasoning


def _merge_evidence_refs(
    direction: ConceptDirection,
    *,
    knowledge_item_ids: list[UUID] | None,
    existing: ReasoningEvidenceRefs | None,
) -> ReasoningEvidenceRefs:
    case_ids = list(direction.reference_case_ids or [])
    if existing is not None:
        case_ids.extend(existing.case_ids)
    rationale = direction.design_rationale
    if rationale is not None:
        for bit in rationale.evidence or []:
            case_id = case_id_from_ref(bit)
            if case_id:
                case_ids.append(case_id)
    case_ids = normalize_case_id_list(case_ids)

    knowledge_ids: list[UUID] = []
    if existing is not None:
        knowledge_ids.extend(existing.knowledge_item_ids)
    if knowledge_item_ids:
        knowledge_ids.extend(knowledge_item_ids)
    return ReasoningEvidenceRefs(
        case_ids=case_ids,
        knowledge_item_ids=knowledge_ids,
    )
