"""Project knowledge items with provenance, reliability, and source tracking."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.citation import Citation
from archium.domain.enums import (
    InformationOrigin,
    InformationReliability,
    KnowledgeItemStatus,
)


class SourceCitation(Citation):
    """Citation to a project document or external public source."""

    document_id: UUID | None = None  # type: ignore[assignment]
    document_name: str = Field(default="")
    url: str | None = None
    source_title: str | None = None
    published_at: date | None = None
    accessed_at: datetime | None = None

    @field_validator("document_name")
    @classmethod
    def _strip_document_name(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _require_source(self) -> SourceCitation:
        if self.document_id is None and not (self.url and self.url.strip()):
            raise ValueError("SourceCitation requires document_id or url")
        if self.document_id is not None and not self.document_name.strip():
            raise ValueError("document_name is required when document_id is set")
        return self

    @classmethod
    def from_citation(cls, citation: Citation) -> SourceCitation:
        return cls.model_validate(citation.model_dump())

    def to_citation(self) -> Citation:
        if self.document_id is None:
            raise ValueError("Cannot convert external-only citation to document Citation")
        return Citation(
            document_id=self.document_id,
            document_name=self.document_name,
            page_number=self.page_number,
            chunk_id=self.chunk_id,
            quote=self.quote,
            confidence=self.confidence,
        )


class ProjectKnowledgeItem(IdentifiedModel, TimestampedModel):
    """A verifiable statement about a project with explicit provenance."""

    project_id: UUID
    statement: str = Field(min_length=1)
    origin: InformationOrigin
    reliability: InformationReliability
    source_citations: list[SourceCitation] = Field(default_factory=list)
    applies_to_current_project: bool = True
    requires_user_confirmation: bool = False
    conflict_group: str | None = Field(default=None, max_length=100)
    status: KnowledgeItemStatus = KnowledgeItemStatus.ACTIVE
    category: str = Field(default="general", min_length=1)
    linked_fact_id: UUID | None = None

    @property
    def is_confirmed(self) -> bool:
        return self.status == KnowledgeItemStatus.CONFIRMED

    @property
    def is_rejected(self) -> bool:
        return self.status == KnowledgeItemStatus.REJECTED

    @property
    def is_reference_only(self) -> bool:
        return (
            self.origin == InformationOrigin.REFERENCE_CASE
            or not self.applies_to_current_project
        )

    @property
    def is_inference(self) -> bool:
        return self.reliability == InformationReliability.INFERENCE

    def confirm(self) -> None:
        self.status = KnowledgeItemStatus.CONFIRMED
        self.reliability = InformationReliability.CONFIRMED
        self.origin = InformationOrigin.USER_CONFIRMED
        self.requires_user_confirmation = False
        self.touch()

    def reject(self) -> None:
        self.status = KnowledgeItemStatus.REJECTED
        self.touch()

    def mark_superseded(self) -> None:
        self.status = KnowledgeItemStatus.SUPERSEDED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)
