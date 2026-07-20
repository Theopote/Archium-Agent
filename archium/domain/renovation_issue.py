"""Renovation issue map for evidence → problem → strategy closed loop."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import Field

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import ApprovalStatus, InformationOrigin
from archium.domain.project_knowledge import SourceCitation


RENOVATION_ISSUE_MAP_LOGICAL_KEY = "project-renovation-issue-map"


class RenovationEvidence(DomainModel):
    """Observed condition or documented fact supporting an issue."""

    id: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    evidence_type: str = Field(default="observation")
    location: str | None = None
    origin: InformationOrigin = InformationOrigin.USER_UPLOAD
    asset_refs: list[str] = Field(default_factory=list)
    source_citations: list[SourceCitation] = Field(default_factory=list)


class RenovationIssue(DomainModel):
    """A diagnosed problem linked to project evidence."""

    id: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1)
    problem_statement: str = Field(min_length=1)
    severity: str = Field(default="medium")
    impact: str | None = None
    linked_evidence_ids: list[str] = Field(default_factory=list)
    origin: InformationOrigin = InformationOrigin.USER_UPLOAD
    source_citations: list[SourceCitation] = Field(default_factory=list)


class RenovationStrategy(DomainModel):
    """A response strategy linked to one or more issues."""

    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1)
    approach: str = Field(min_length=1)
    category: str = Field(default="strategy")
    linked_issue_ids: list[str] = Field(default_factory=list)
    phasing: str | None = None
    scope_note: str | None = None
    origin: InformationOrigin = InformationOrigin.USER_UPLOAD


class RenovationIssueMap(IdentifiedModel, VersionedModel, TimestampedModel):
    """Structured renovation diagnosis for retrofit / renewal presentations."""

    project_id: UUID
    lineage_id: UUID = Field(default_factory=uuid4)
    building_summary: str = Field(min_length=1)
    condition_overview: str | None = None
    evidence_items: list[RenovationEvidence] = Field(default_factory=list)
    issues: list[RenovationIssue] = Field(default_factory=list)
    strategies: list[RenovationStrategy] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT

    @property
    def is_approved(self) -> bool:
        return self.approval_status == ApprovalStatus.APPROVED

    def approve(self) -> None:
        self.approval_status = ApprovalStatus.APPROVED
        self.touch()

    def reject(self) -> None:
        self.approval_status = ApprovalStatus.REJECTED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)
