"""ArtDirection — presentation-level visual language (not per-slide coordinates)."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import ApprovalStatus


class ArtDirection(IdentifiedModel, VersionedModel, TimestampedModel):
    """Defines the visual language for an entire deliverable."""

    project_id: UUID
    deliverable_id: str | None = None
    presentation_id: UUID | None = None
    concept_name: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1)
    visual_tone: list[str] = Field(default_factory=list)
    emotional_keywords: list[str] = Field(default_factory=list)
    palette_strategy: str = Field(min_length=1)
    typography_strategy: str = Field(min_length=1)
    grid_strategy: str = Field(min_length=1)
    image_strategy: str = Field(min_length=1)
    drawing_strategy: str = Field(min_length=1)
    diagram_strategy: str = Field(min_length=1)
    annotation_strategy: str = Field(min_length=1)
    cover_strategy: str = Field(min_length=1)
    section_strategy: str = Field(min_length=1)
    content_strategy: str = Field(min_length=1)
    closing_strategy: str = Field(min_length=1)
    pacing_strategy: str = Field(min_length=1)
    consistency_rules: list[str] = Field(default_factory=list)
    forbidden_styles: list[str] = Field(default_factory=list)
    design_system_id: UUID | None = None
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT

    def approve(self) -> None:
        self.approval_status = ApprovalStatus.APPROVED
        self.touch()

    def reject(self) -> None:
        self.approval_status = ApprovalStatus.REJECTED
        self.touch()
