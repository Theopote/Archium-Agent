"""Explicit Fact ↔ Knowledge ↔ Manuscript mapping with lossy-field warnings (DOM-008 / KN-002)."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.fact import ProjectFact
from archium.domain.presentation_manuscript import (
    ManuscriptFact,
    PresentationEvidenceItem,
)
from archium.domain.project_knowledge import ProjectKnowledgeItem

# Fields collapsed or omitted when ProjectFact → ProjectKnowledgeItem.
DROPPED_FACT_TO_KNOWLEDGE: frozenset[str] = frozenset(
    {
        "key",
        "value",
        "unit",
        "confidence",
        "alternate_values",
        "verification_status",
        "label",
    }
)

# Fields omitted when ProjectKnowledgeItem → ManuscriptFact.
DROPPED_KNOWLEDGE_TO_MANUSCRIPT: frozenset[str] = frozenset(
    {
        "origin",
        "reliability",
        "status",
        "category",
        "conflict_group",
        "requires_user_confirmation",
        "applies_to_current_project",
        "design_knowledge",
    }
)


@dataclass(frozen=True, slots=True)
class MappingResult:
    """Mapped artifact plus machine-readable lossy-field warnings."""

    warnings: tuple[str, ...]


def _drop_warnings(prefix: str, fields: frozenset[str]) -> tuple[str, ...]:
    return tuple(sorted(f"{prefix}{name}" for name in fields))


def project_fact_to_knowledge_item(
    fact: ProjectFact,
    *,
    from_reference: bool = False,
) -> tuple[ProjectKnowledgeItem, MappingResult]:
    """Fact → Knowledge with ``linked_fact_id`` and DROPPED_FACT_* warnings."""
    from archium.application.knowledge_isolation import fact_to_knowledge_item

    item = fact_to_knowledge_item(fact, from_reference=from_reference)
    return item, MappingResult(warnings=_drop_warnings("DROPPED_FACT_", DROPPED_FACT_TO_KNOWLEDGE))


def knowledge_item_to_manuscript_fact(
    item: ProjectKnowledgeItem,
    *,
    citation_ids: list[str] | None = None,
    verified: bool = False,
    confidence: float | None = None,
) -> tuple[ManuscriptFact, MappingResult]:
    """Knowledge → ManuscriptFact with typed IDs and DROPPED_KNOWLEDGE_* warnings."""
    ids = list(citation_ids or [])
    if confidence is None:
        confidence = 1.0 if verified else 0.6
    fact = ManuscriptFact(
        statement=item.statement,
        source_id=str(item.id),
        citation_ids=ids,
        confidence=confidence,
        verified=verified,
        knowledge_item_id=item.id,
        linked_fact_id=item.linked_fact_id,
    )
    return fact, MappingResult(
        warnings=_drop_warnings("DROPPED_KNOWLEDGE_", DROPPED_KNOWLEDGE_TO_MANUSCRIPT)
    )


def knowledge_item_to_evidence(
    item: ProjectKnowledgeItem,
    *,
    citation_id: str | None = None,
    verified: bool = False,
    confidence: float = 0.6,
) -> PresentationEvidenceItem:
    """Companion evidence row sharing the same typed Knowledge/Fact links."""
    return PresentationEvidenceItem(
        evidence_type="document_quote",
        summary=item.statement,
        source_id=str(item.id),
        citation_id=citation_id,
        confidence=confidence,
        verified=verified,
        knowledge_item_id=item.id,
        linked_fact_id=item.linked_fact_id,
        asset_origin="project_upload",
    )


def link_invariant_issues(
    *,
    fact: ProjectFact | None = None,
    knowledge: ProjectKnowledgeItem | None = None,
    manuscript_fact: ManuscriptFact | None = None,
) -> list[str]:
    """DOM-008: report broken Fact↔Knowledge↔Manuscript ID chains."""
    issues: list[str] = []
    if knowledge is not None and fact is not None and knowledge.linked_fact_id != fact.id:
        issues.append(
            f"knowledge.linked_fact_id={knowledge.linked_fact_id} != fact.id={fact.id}"
        )
    if manuscript_fact is not None and knowledge is not None:
        if manuscript_fact.knowledge_item_id != knowledge.id:
            issues.append(
                "manuscript.knowledge_item_id="
                f"{manuscript_fact.knowledge_item_id} != knowledge.id={knowledge.id}"
            )
        if manuscript_fact.source_id != str(knowledge.id):
            issues.append(
                f"manuscript.source_id={manuscript_fact.source_id!r} "
                f"!= str(knowledge.id)={str(knowledge.id)!r}"
            )
        if (
            knowledge.linked_fact_id is not None
            and manuscript_fact.linked_fact_id != knowledge.linked_fact_id
        ):
            issues.append(
                "manuscript.linked_fact_id="
                f"{manuscript_fact.linked_fact_id} != knowledge.linked_fact_id="
                f"{knowledge.linked_fact_id}"
            )
    if manuscript_fact is not None and fact is not None:
        if manuscript_fact.linked_fact_id != fact.id:
            issues.append(
                f"manuscript.linked_fact_id={manuscript_fact.linked_fact_id} != fact.id={fact.id}"
            )
    return issues
