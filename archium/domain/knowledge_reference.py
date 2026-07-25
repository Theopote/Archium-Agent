"""Unified knowledge reference — scored hit across Project Knowledge Space."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.architectural_chunk import ArchitecturalChunkType


class KnowledgeSourceKind(StrEnum):
    FACT = "fact"
    DOCUMENT_CHUNK = "document_chunk"
    KNOWLEDGE_ITEM = "knowledge_item"
    ARCHITECTURE_CASE = "architecture_case"


class KnowledgeUsage(StrEnum):
    EVIDENCE = "evidence"
    DESIGN_JUDGMENT = "design_judgment"
    ILLUSTRATIVE = "illustrative"
    BACKGROUND = "background"


class KnowledgeReference(DomainModel):
    """One retrieval hit with credibility dimensions (not cosine alone)."""

    source_kind: KnowledgeSourceKind
    source_id: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=4000)
    title: str = ""
    similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    authority: float = Field(default=0.5, ge=0.0, le=1.0)
    transferability: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fused score: similarity × authority × transferability blend.",
    )
    usage: KnowledgeUsage = KnowledgeUsage.BACKGROUND
    architectural_type: ArchitecturalChunkType | None = None
    project_id: UUID | None = None
    extra: dict[str, object] = Field(default_factory=dict)

    def to_prompt_line(self) -> str:
        label = self.title.strip() or self.source_kind.value
        scores = (
            f"sim={self.similarity:.2f} auth={self.authority:.2f} "
            f"xfer={self.transferability:.2f} rel={self.relevance:.2f}"
        )
        type_bit = (
            f" · {self.architectural_type.value}"
            if self.architectural_type is not None
            else ""
        )
        snippet = self.content.strip().replace("\n", " ")[:280]
        return f"- [{self.source_kind.value}/{self.usage.value}{type_bit}] {label} ({scores}): {snippet}"


def fuse_relevance(
    *,
    similarity: float,
    authority: float,
    transferability: float,
    usage: KnowledgeUsage | None = None,
    has_citations: bool = False,
) -> float:
    """Blend retrieval similarity with credibility dimensions."""
    from archium.application.retrieval_credibility import rank_relevance

    return rank_relevance(
        similarity=similarity,
        authority=authority,
        transferability=transferability,
        usage=usage,
        has_citations=has_citations,
    )
