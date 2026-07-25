"""Claim index pointers — KnowledgeState indexes truth stores, does not own them."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class KnowledgeClaimKind(StrEnum):
    """Where a claim's authoritative body lives."""

    FACT = "fact"
    KNOWLEDGE_ITEM = "knowledge_item"
    ASSESSMENT = "assessment"  # LLM/rule known without linked entity


class KnowledgeClaimRef(DomainModel):
    """Pointer into Fact / KnowledgeItem (or assessment-only summary).

    Do not dump full statements, citations, or process state here.
    """

    key: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=500)
    kind: KnowledgeClaimKind = KnowledgeClaimKind.ASSESSMENT
    fact_id: UUID | None = None
    knowledge_item_id: UUID | None = None
    status: str = Field(default="", max_length=40)
    confirmed: bool = False


class KnowledgeUnknownRef(DomainModel):
    """Structured open gap — preferred over free-text unknown lists."""

    description: str = Field(min_length=1, max_length=500)
    category: str = Field(default="", max_length=80)
    blocking: bool = False
    related_keys: list[str] = Field(default_factory=list)
    gap_id: str = Field(default="", max_length=120)
