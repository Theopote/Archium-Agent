"""Presentation manuscript — research middle layer between knowledge and outline."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.citation import Citation

MANUSCRIPT_LOGICAL_KEY = "presentation-manuscript"


class ManuscriptFact(DomainModel):
    """A verified or candidate fact eligible for presentation use."""

    id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    statement: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    citation_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verified: bool = False
    knowledge_item_id: UUID | None = None

    @field_validator("statement", "source_id")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be empty")
        return stripped


class EvidenceItem(DomainModel):
    """Catalog entry for evidence that can support a slide argument."""

    id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    evidence_type: Literal[
        "project_photo",
        "drawing",
        "metric",
        "document_quote",
        "historic_archive",
        "reference_case",
        "public_research",
    ]
    summary: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    asset_id: UUID | None = None
    citation_id: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verified: bool = False
    # Never promote reference_template assets into project evidence.
    asset_origin: Literal[
        "project_upload",
        "public_research",
        "reference_case",
        "reference_template",
        "ai_generated",
        "stock_image",
    ] = "project_upload"

    @field_validator("summary", "source_id")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be empty")
        return stripped


class CitationReference(DomainModel):
    """Stable citation handle used inside a manuscript."""

    id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    citation: Citation
    label: str = ""


class ManuscriptSection(DomainModel):
    """A narrative section that later maps to outline chapters / slides."""

    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1)
    argument: str = Field(min_length=1)
    key_points: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    fact_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    recommended_slide_types: list[str] = Field(default_factory=list)
    order: int = Field(default=0, ge=0)


class ManuscriptStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    SUPERSEDED = "superseded"


class PresentationManuscript(IdentifiedModel, VersionedModel, TimestampedModel):
    """Stable research product between ProjectKnowledge and OutlinePlan."""

    project_id: UUID
    presentation_id: UUID | None = None
    lineage_id: UUID = Field(default_factory=uuid4)
    logical_key: str = Field(default=MANUSCRIPT_LOGICAL_KEY, max_length=200)

    title: str = Field(min_length=1, max_length=500)
    project_summary: str = Field(min_length=1)
    narrative_thesis: str = Field(min_length=1)

    verified_facts: list[ManuscriptFact] = Field(default_factory=list)
    sections: list[ManuscriptSection] = Field(default_factory=list)
    evidence_catalog: list[EvidenceItem] = Field(default_factory=list)
    citations: list[CitationReference] = Field(default_factory=list)

    unresolved_questions: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)

    status: ManuscriptStatus = ManuscriptStatus.DRAFT

    def fact_by_id(self, fact_id: str) -> ManuscriptFact | None:
        for fact in self.verified_facts:
            if fact.id == fact_id:
                return fact
        return None

    def evidence_by_id(self, evidence_id: str) -> EvidenceItem | None:
        for item in self.evidence_catalog:
            if item.id == evidence_id:
                return item
        return None

    def section_by_id(self, section_id: str) -> ManuscriptSection | None:
        for section in self.sections:
            if section.id == section_id:
                return section
        return None

    def project_evidence_only(self) -> list[EvidenceItem]:
        """Evidence safe for project slides (excludes reference template assets)."""
        return [
            item
            for item in self.evidence_catalog
            if item.asset_origin != "reference_template"
        ]

    def mark_ready(self) -> None:
        self.status = ManuscriptStatus.READY
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)
