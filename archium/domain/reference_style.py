"""Reference style profile extracted from reference-style documents."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import Field

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import ApprovalStatus


REFERENCE_STYLE_PROFILE_LOGICAL_KEY = "project-reference-style-profile"


class StyleColorCue(DomainModel):
    """A color observation from reference material."""

    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    usage: str = Field(default="accent")


class StyleTypographyCue(DomainModel):
    """Typography observation from reference material."""

    id: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1)
    description: str = Field(min_length=1)


class StyleLayoutCue(DomainModel):
    """Layout or composition pattern from reference material."""

    id: str = Field(min_length=1, max_length=100)
    pattern: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ReferenceStyleProfile(IdentifiedModel, VersionedModel, TimestampedModel):
    """Visual language cues from reference-style files — not project facts."""

    project_id: UUID
    lineage_id: UUID = Field(default_factory=uuid4)
    style_name: str = Field(min_length=1)
    source_document_ids: list[str] = Field(default_factory=list)
    mood_keywords: list[str] = Field(default_factory=list)
    color_cues: list[StyleColorCue] = Field(default_factory=list)
    typography_cues: list[StyleTypographyCue] = Field(default_factory=list)
    layout_cues: list[StyleLayoutCue] = Field(default_factory=list)
    image_treatment: str = Field(default="")
    graphic_elements: list[str] = Field(default_factory=list)
    pacing_density: str = Field(default="balanced")
    do_rules: list[str] = Field(default_factory=list)
    dont_rules: list[str] = Field(default_factory=list)
    adaptation_notes: list[str] = Field(default_factory=list)
    unsupported_observations: list[str] = Field(default_factory=list)
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
