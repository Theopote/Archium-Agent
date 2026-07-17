"""Presentation, brief, and storyline models."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, model_validator

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import ApprovalStatus, PresentationStatus, PresentationType


class Presentation(IdentifiedModel, TimestampedModel):
    """A presentation belonging to a project."""

    project_id: UUID
    title: str = Field(min_length=1, max_length=500)
    status: PresentationStatus = PresentationStatus.DRAFT
    description: str | None = None
    current_brief_id: UUID | None = None
    current_storyline_id: UUID | None = None

    def touch(self) -> None:
        TimestampedModel.touch(self)


class PresentationBrief(IdentifiedModel, VersionedModel, TimestampedModel):
    """Structured briefing document defining presentation goals and constraints."""

    project_id: UUID
    presentation_id: UUID
    title: str = Field(min_length=1, max_length=500)
    presentation_type: PresentationType = PresentationType.OTHER
    audience: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    duration_minutes: int = Field(default=20, ge=1, le=480)
    target_slide_count: int = Field(default=20, ge=1, le=200)
    core_message: str = Field(min_length=1)
    decisions_required: list[str] = Field(default_factory=list)
    audience_concerns: list[str] = Field(default_factory=list)
    tone: str = "professional"
    required_sections: list[str] = Field(default_factory=list)
    excluded_topics: list[str] = Field(default_factory=list)
    language: str = Field(default="zh-CN", min_length=2)
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT

    def approve(self) -> None:
        self.approval_status = ApprovalStatus.APPROVED
        self.touch()

    def reject(self) -> None:
        self.approval_status = ApprovalStatus.REJECTED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)


class Chapter(DomainModel):
    """A narrative chapter within a storyline."""

    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1)
    key_message: str = Field(min_length=1)
    order: int = Field(ge=0)
    estimated_slide_count: int = Field(default=1, ge=1)


class Storyline(IdentifiedModel, VersionedModel, TimestampedModel):
    """Narrative structure for a presentation."""

    presentation_id: UUID
    thesis: str = Field(min_length=1)
    narrative_pattern: str = Field(default="problem_solution", min_length=1)
    chapters: list[Chapter] = Field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT

    @model_validator(mode="after")
    def _validate_chapter_order(self) -> Storyline:
        if not self.chapters:
            return self
        orders = [chapter.order for chapter in self.chapters]
        if len(orders) != len(set(orders)):
            raise ValueError("chapter order values must be unique")
        return self

    def approve(self) -> None:
        self.approval_status = ApprovalStatus.APPROVED
        self.touch()

    def reject(self) -> None:
        self.approval_status = ApprovalStatus.REJECTED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)
