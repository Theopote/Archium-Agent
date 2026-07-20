"""Rules separating project facts from reference material and unverified claims."""

from __future__ import annotations

from archium.domain.enums import (
    DocumentPurpose,
    InformationOrigin,
    InformationReliability,
    KnowledgeItemStatus,
    VerificationStatus,
)
from archium.domain.fact import ProjectFact
from archium.domain.project_knowledge import ProjectKnowledgeItem

# Keys that must be user-confirmed before entering formal slide generation.
CRITICAL_FACT_KEYS: frozenset[str] = frozenset(
    {
        "site_area",
        "building_area",
        "plot_ratio",
        "building_density",
        "height",
        "floors",
        "bed_count",
        "heritage_level",
        "structure_status",
        "construction_cost",
        "property_rights",
    }
)


def verification_to_reliability(status: VerificationStatus) -> InformationReliability:
    mapping = {
        VerificationStatus.USER_CONFIRMED: InformationReliability.CONFIRMED,
        VerificationStatus.EXTRACTED: InformationReliability.HIGH_CONFIDENCE,
        VerificationStatus.INFERRED: InformationReliability.INFERENCE,
        VerificationStatus.CONFLICTED: InformationReliability.CONFLICTING,
        VerificationStatus.REJECTED: InformationReliability.UNVERIFIED,
    }
    return mapping[status]


def verification_to_origin(
    status: VerificationStatus,
    *,
    from_reference: bool = False,
) -> InformationOrigin:
    if from_reference:
        return InformationOrigin.REFERENCE_CASE
    if status == VerificationStatus.USER_CONFIRMED:
        return InformationOrigin.USER_CONFIRMED
    if status == VerificationStatus.INFERRED:
        return InformationOrigin.SYSTEM_INFERENCE
    return InformationOrigin.USER_UPLOAD


def fact_to_knowledge_item(
    fact: ProjectFact,
    *,
    from_reference: bool = False,
) -> ProjectKnowledgeItem:
    from archium.domain.enums import KnowledgeItemStatus
    from archium.domain.project_knowledge import SourceCitation

    status = KnowledgeItemStatus.REJECTED
    if fact.verification_status != VerificationStatus.REJECTED:
        status = (
            KnowledgeItemStatus.CONFIRMED
            if fact.is_confirmed
            else KnowledgeItemStatus.ACTIVE
        )

    return ProjectKnowledgeItem(
        id=fact.id,
        project_id=fact.project_id,
        statement=f"{fact.label}: {fact.value}{(' ' + fact.unit) if fact.unit else ''}",
        origin=verification_to_origin(fact.verification_status, from_reference=from_reference),
        reliability=verification_to_reliability(fact.verification_status),
        source_citations=[SourceCitation.from_citation(c) for c in fact.source_citations],
        applies_to_current_project=not from_reference,
        requires_user_confirmation=(
            fact.key in CRITICAL_FACT_KEYS and not fact.is_confirmed
        ),
        conflict_group=fact.conflict_group,
        status=status,
        category=fact.category,
        linked_fact_id=fact.id,
        created_at=fact.created_at,
        updated_at=fact.updated_at,
    )


def document_purpose_from_metadata(metadata: dict[str, object]) -> DocumentPurpose:
    raw = metadata.get("purpose") or metadata.get("document_purpose")
    if raw is None:
        return DocumentPurpose.PROJECT_MATERIAL
    try:
        return DocumentPurpose(str(raw))
    except ValueError:
        return DocumentPurpose.PROJECT_MATERIAL


def is_reference_document(metadata: dict[str, object]) -> bool:
    purpose = document_purpose_from_metadata(metadata)
    return purpose in {
        DocumentPurpose.REFERENCE_CASE,
        DocumentPurpose.REFERENCE_STYLE,
        DocumentPurpose.PUBLIC_RESEARCH,
    }


def is_eligible_for_generation(item: ProjectKnowledgeItem) -> bool:
    """Return True when a knowledge item may enter Brief/Storyline/Slide context."""
    if item.is_rejected or item.status == KnowledgeItemStatus.SUPERSEDED:
        return False
    if item.is_reference_only:
        return False
    if item.reliability == InformationReliability.CONFLICTING:
        return False
    if not item.source_citations and item.origin == InformationOrigin.PUBLIC_RESEARCH:
        return False
    if item.reliability == InformationReliability.INFERENCE and not item.is_confirmed:
        return False
    if item.requires_user_confirmation and not item.is_confirmed:
        return False
    return not (
        item.reliability == InformationReliability.UNVERIFIED
        and not item.source_citations
        and item.origin != InformationOrigin.USER_CONFIRMED
    )


def is_fact_eligible_for_generation(
    fact: ProjectFact,
    *,
    reference_document_ids: set[str] | None = None,
) -> bool:
    if fact.verification_status == VerificationStatus.REJECTED:
        return False
    if fact.verification_status == VerificationStatus.CONFLICTED:
        return False
    if fact.verification_status == VerificationStatus.INFERRED and not fact.is_confirmed:
        return False
    if fact.key in CRITICAL_FACT_KEYS and not fact.is_confirmed:
        return False
    return not (
        reference_document_ids
        and fact.source_citations
        and all(str(c.document_id) in reference_document_ids for c in fact.source_citations)
    )


def filter_generation_knowledge(
    items: list[ProjectKnowledgeItem],
) -> list[ProjectKnowledgeItem]:
    return [item for item in items if is_eligible_for_generation(item)]


def filter_generation_facts(
    facts: list[ProjectFact],
    *,
    reference_document_ids: set[str] | None = None,
) -> list[ProjectFact]:
    return [
        fact
        for fact in facts
        if is_fact_eligible_for_generation(
            fact,
            reference_document_ids=reference_document_ids,
        )
    ]
