"""VisualIntent — bridge between SlideSpec content and LayoutPlan geometry."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import ApprovalStatus
from archium.domain.visual.enums import (
    ContinuityRole,
    DensityLevel,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.vision_generation import ImageRequest
from archium.domain.visual.visual_grammar import PageArchetype


class VisualIntent(IdentifiedModel, VersionedModel, TimestampedModel):
    """Per-slide visual communication intent (no coordinates)."""

    slide_id: UUID
    presentation_id: UUID | None = None
    art_direction_id: UUID | None = None
    communication_goal: str = Field(min_length=1)
    audience_takeaway: str = Field(min_length=1)
    visual_priority: str = Field(min_length=1)
    dominant_content_type: VisualContentType
    hero_asset_id: UUID | None = None
    supporting_asset_ids: list[UUID] = Field(default_factory=list)
    hierarchy: list[str] = Field(default_factory=list)
    reading_order: list[str] = Field(default_factory=list)
    preferred_layout_families: list[LayoutFamily] = Field(default_factory=list)
    composition_strategy: str = ""
    image_treatment: str = ""
    annotation_strategy: str = ""
    background_strategy: str = ""
    density_level: DensityLevel = DensityLevel.BALANCED
    emotional_tone: str = ""
    continuity_role: ContinuityRole = ContinuityRole.EXPLANATION
    page_archetype: PageArchetype | None = None
    image_request: ImageRequest | None = None
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT

    def approve(self) -> None:
        self.approval_status = ApprovalStatus.APPROVED
        self.touch()
