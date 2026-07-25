"""Credibility dimensions for architectural retrieval ranking.

Similarity alone is not enough — authority and transferability gate how
hits may be used as evidence vs illustration.
"""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.architectural_chunk import ArchitecturalChunkType
from archium.domain.document import DocumentChunk
from archium.domain.enums import InformationOrigin, InformationReliability, VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.knowledge_reference import KnowledgeUsage
from archium.domain.project_knowledge import ProjectKnowledgeItem

_RELIABILITY_AUTHORITY: dict[InformationReliability, float] = {
    InformationReliability.CONFIRMED: 0.95,
    InformationReliability.HIGH_CONFIDENCE: 0.82,
    InformationReliability.UNVERIFIED: 0.42,
    InformationReliability.INFERENCE: 0.32,
    InformationReliability.CONFLICTING: 0.18,
}

_ORIGIN_TRANSFER: dict[InformationOrigin, float] = {
    InformationOrigin.USER_UPLOAD: 0.9,
    InformationOrigin.USER_CONFIRMED: 1.0,
    InformationOrigin.PUBLIC_RESEARCH: 0.72,
    InformationOrigin.REFERENCE_CASE: 0.55,
    InformationOrigin.SYSTEM_INFERENCE: 0.4,
}


@dataclass(frozen=True)
class CredibilityScores:
    authority: float
    transferability: float
    has_citations: bool = False


def reliability_authority(reliability: InformationReliability) -> float:
    return _RELIABILITY_AUTHORITY.get(reliability, 0.4)


def score_fact_credibility(fact: ProjectFact) -> CredibilityScores:
    if fact.is_confirmed:
        authority = 0.94
    else:
        authority = min(0.78, 0.38 + float(fact.confidence) * 0.45)
    if fact.verification_status == VerificationStatus.CONFLICTED:
        authority = min(authority, 0.25)
    has_citations = bool(fact.source_citations)
    if has_citations:
        authority = min(1.0, authority + 0.06)
    return CredibilityScores(
        authority=authority,
        transferability=1.0,
        has_citations=has_citations,
    )


def score_chunk_credibility(
    chunk: DocumentChunk,
    *,
    preferred_types: list[ArchitecturalChunkType] | None = None,
) -> CredibilityScores:
    preferred = {item.value for item in (preferred_types or [])}
    arch = str(chunk.metadata.get("architectural_type") or chunk.architectural_type.value)
    if chunk.content_type == "asset_caption":
        authority = 0.52
        transferability = 0.6
    else:
        authority = 0.72
        transferability = 0.78 if arch != ArchitecturalChunkType.GENERAL.value else 0.55
    if preferred and arch in preferred:
        transferability = min(1.0, transferability + 0.15)
        authority = min(1.0, authority + 0.04)
    return CredibilityScores(authority=authority, transferability=transferability)


def score_knowledge_credibility(
    item: ProjectKnowledgeItem,
    *,
    preferred_types: list[ArchitecturalChunkType] | None = None,
) -> CredibilityScores:
    authority = reliability_authority(item.reliability)
    has_citations = bool(item.source_citations)
    if has_citations:
        authority = min(1.0, authority + 0.08)
    if item.is_confirmed:
        authority = min(1.0, max(authority, 0.9))
    if item.requires_user_confirmation and not item.is_confirmed:
        authority = min(authority, 0.45)

    dk = item.design_knowledge
    transferability = _ORIGIN_TRANSFER.get(item.origin, 0.5)
    if dk is not None and dk.has_substance:
        transferability = max(transferability, 0.82)
        if dk.spatial_translation.strip() or dk.principle.strip():
            transferability = min(1.0, transferability + 0.06)
    if not item.applies_to_current_project:
        transferability = min(transferability, 0.45)

    preferred = set(preferred_types or [])
    if preferred and dk is not None and dk.has_substance:
        design_types = {
            ArchitecturalChunkType.SPATIAL_STRATEGY,
            ArchitecturalChunkType.DESIGN_CONCEPT,
            ArchitecturalChunkType.MATERIAL_STRATEGY,
        }
        if preferred & design_types:
            transferability = min(1.0, transferability + 0.1)

    return CredibilityScores(
        authority=authority,
        transferability=transferability,
        has_citations=has_citations,
    )


def rank_relevance(
    *,
    similarity: float,
    authority: float,
    transferability: float,
    usage: KnowledgeUsage | None = None,
    has_citations: bool = False,
) -> float:
    """Deeper credibility-aware blend than linear similarity alone."""
    sim = _clamp(similarity)
    auth = _clamp(authority)
    xfer = _clamp(transferability)
    if has_citations:
        auth = min(1.0, auth + 0.05)

    # Base blend (same weights as KnowledgeReference.fuse_relevance)
    score = (0.45 * sim) + (0.30 * auth) + (0.25 * xfer)

    # Authority gates — similar ≠ usable as project evidence
    if auth < 0.35:
        score *= 0.55
    elif auth < 0.5:
        score *= 0.82

    if usage == KnowledgeUsage.EVIDENCE and auth < 0.55:
        score *= 0.72
    if usage == KnowledgeUsage.ILLUSTRATIVE:
        # Illustration can tolerate lower authority slightly
        score = min(1.0, score + 0.02)

    # High transferability + decent similarity → design judgment boost
    if xfer >= 0.8 and sim >= 0.45:
        score = min(1.0, score + 0.06)

    # Low transferability caps relevance even if text-similar
    if xfer < 0.4:
        score = min(score, 0.45)

    return _clamp(score)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
