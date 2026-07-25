"""Build KnowledgeState claim index from Fact / KnowledgeItem evidence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.context_evidence import ProjectEvidencePack, gather_project_evidence
from archium.application.knowledge_gap_detection import KnowledgeGapEntry
from archium.domain.enums import KnowledgeItemStatus, VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.intent.knowledge_claim import (
    KnowledgeClaimKind,
    KnowledgeClaimRef,
    KnowledgeUnknownRef,
)
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.project_knowledge import ProjectKnowledgeItem


def merge_claim_index_into_state(
    state: KnowledgeState,
    evidence: ProjectEvidencePack,
) -> KnowledgeState:
    """Attach claim/unknown index from evidence; keep known/unknown as projections."""
    claims = claims_from_evidence(
        facts=evidence.indexed_facts,
        knowledge_items=evidence.indexed_knowledge_items,
        llm_known=state.known,
    )
    open_unknowns = unknowns_from_evidence(
        gaps=evidence.indexed_gaps,
        llm_unknown=state.unknown or state.missing_information,
    )
    known = known_projection(claims, fallback=state.known)
    unknown = [item.description for item in open_unknowns]
    source_count = evidence.document_count + (
        1 if evidence.chunk_excerpts.strip() else 0
    )
    fact_count = (
        evidence.confirmed_fact_count
        + evidence.extracted_fact_count
        + evidence.pending_fact_count
    )
    return state.model_copy(
        update={
            "claims": claims,
            "open_unknowns": open_unknowns,
            "known": known,
            "unknown": unknown,
            "missing_information": unknown,
            "fact_count": fact_count,
            "source_count": source_count,
            "knowledge_item_count": evidence.knowledge_item_count,
            "cognition_stale": False,
        }
    )


def refresh_claim_index_only(
    session: Session,
    project_id: UUID,
    *,
    mark_stale: bool = False,
    history_reason: str = "index_refresh",
) -> KnowledgeState | None:
    """Deterministic claim-index refresh without LLM (incremental / fallback path)."""
    from archium.infrastructure.database.repositories import ProjectRepository

    project = ProjectRepository(session).get_by_id(project_id)
    if project is None or project.knowledge_state is None:
        return None
    evidence = gather_project_evidence(session, project_id)
    updated = merge_claim_index_into_state(project.knowledge_state, evidence)
    if mark_stale:
        updated = updated.model_copy(
            update={"cognition_stale": True, "source": "index_refresh"}
        )
    else:
        updated = updated.model_copy(update={"source": "index_refresh"})
    project.knowledge_state = updated
    project.knowledge_state_history = project.knowledge_state_history.append_from_state(
        updated,
        reason=history_reason or "index_refresh",
        reason_detail="deterministic claim index refresh",
    )
    project.touch()
    ProjectRepository(session).update(project)
    session.commit()
    return updated


def claims_from_evidence(
    *,
    facts: tuple[ProjectFact, ...] | list[ProjectFact],
    knowledge_items: tuple[ProjectKnowledgeItem, ...] | list[ProjectKnowledgeItem],
    llm_known: dict[str, str] | None = None,
) -> list[KnowledgeClaimRef]:
    claims: list[KnowledgeClaimRef] = []
    covered_keys: set[str] = set()

    for fact in facts:
        if fact.verification_status == VerificationStatus.REJECTED:
            continue
        summary = f"{fact.label}: {_short_value(fact.value)}"
        claims.append(
            KnowledgeClaimRef(
                key=fact.key,
                summary=summary[:500],
                kind=KnowledgeClaimKind.FACT,
                fact_id=fact.id,
                status=fact.verification_status.value,
                confirmed=fact.is_confirmed,
            )
        )
        covered_keys.add(fact.key.lower())

    for item in knowledge_items:
        if item.status == KnowledgeItemStatus.REJECTED:
            continue
        if item.is_reference_only:
            continue
        key = f"knowledge:{item.category}:{str(item.id)[:8]}"
        claims.append(
            KnowledgeClaimRef(
                key=key,
                summary=(item.statement or "")[:500],
                kind=KnowledgeClaimKind.KNOWLEDGE_ITEM,
                knowledge_item_id=item.id,
                status=item.status.value,
                confirmed=item.is_confirmed,
            )
        )

    for raw_key, value in (llm_known or {}).items():
        key = str(raw_key).strip()
        if not key or key.lower() in covered_keys:
            continue
        if any(c.key == key for c in claims):
            continue
        claims.append(
            KnowledgeClaimRef(
                key=key,
                summary=str(value).strip()[:500],
                kind=KnowledgeClaimKind.ASSESSMENT,
                status="assessment",
                confirmed=False,
            )
        )
    return claims


def unknowns_from_evidence(
    *,
    gaps: tuple[KnowledgeGapEntry, ...] | list[KnowledgeGapEntry],
    llm_unknown: list[str] | None = None,
) -> list[KnowledgeUnknownRef]:
    open_unknowns: list[KnowledgeUnknownRef] = []
    seen: set[str] = set()
    for gap in gaps:
        desc = (gap.description or "").strip()
        if not desc:
            continue
        norm = desc.lower()
        if norm in seen:
            continue
        seen.add(norm)
        open_unknowns.append(
            KnowledgeUnknownRef(
                description=desc[:500],
                category=gap.category or "",
                blocking=bool(gap.blocking),
                related_keys=list(gap.related_keys or ()),
                gap_id=gap.gap_id or "",
            )
        )
    for text in llm_unknown or []:
        desc = str(text).strip()
        if not desc:
            continue
        norm = desc.lower()
        if norm in seen:
            continue
        # Skip if already covered by a gap description substring match
        if any(norm in s or s in norm for s in seen):
            continue
        seen.add(norm)
        open_unknowns.append(
            KnowledgeUnknownRef(
                description=desc[:500],
                category="assessment",
                blocking=False,
            )
        )
    return open_unknowns


def known_projection(
    claims: list[KnowledgeClaimRef],
    *,
    fallback: dict[str, str] | None = None,
) -> dict[str, str]:
    """Compat known dict: prefer linked claims, then assessment keys."""
    known: dict[str, str] = {}
    for claim in claims:
        if claim.kind == KnowledgeClaimKind.KNOWLEDGE_ITEM:
            # Keep knowledge items out of flat known keys (too many / long)
            continue
        value = claim.summary
        if claim.kind == KnowledgeClaimKind.FACT and ":" in claim.summary:
            value = claim.summary.split(":", 1)[-1].strip()
        known[claim.key] = value[:200]
    for key, value in (fallback or {}).items():
        known.setdefault(str(key), str(value)[:200])
    return known


def _short_value(value: object) -> str:
    text = str(value).strip()
    return text if len(text) <= 120 else text[:117] + "…"
