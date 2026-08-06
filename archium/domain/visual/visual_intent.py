"""VisualIntent — bridge between SlideSpec content and LayoutPlan geometry."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from archium.domain._base import IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import ApprovalStatus
from archium.domain.visual.composition_strategy import CompositionStrategy
from archium.domain.visual.enums import (
    ContinuityRole,
    DensityLevel,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.page_direction import PageDirection
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

    # Structured composition strategy (v0.3 upgrade from string)
    composition_strategy: CompositionStrategy | str | None = Field(
        default=None,
        description="Structured design judgment (CompositionStrategy) or legacy string",
    )

    image_treatment: str = ""
    annotation_strategy: str = ""
    background_strategy: str = ""
    density_level: DensityLevel = DensityLevel.BALANCED
    emotional_tone: str = ""
    continuity_role: ContinuityRole = ContinuityRole.EXPLANATION
    page_archetype: PageArchetype | None = None
    # v0.3 Page Director output (structured creative direction; no geometry).
    page_direction: PageDirection | None = None
    # v0.3 Expression Mode id + locked layout variant (Phase 2).
    expression_mode_id: str | None = None
    preferred_layout_variant: str | None = None
    image_request: ImageRequest | None = None
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT

    @field_validator("composition_strategy", mode="before")
    @classmethod
    def _coerce_composition_strategy(cls, v: str | dict | CompositionStrategy | None) -> CompositionStrategy | str | None:
        """Backward compatibility: accept string, dict, or CompositionStrategy."""
        if v is None or isinstance(v, (CompositionStrategy, str)):
            return v
        if isinstance(v, dict):
            return CompositionStrategy.model_validate(v)
        return v

    def approve(self) -> None:
        self.approval_status = ApprovalStatus.APPROVED
        self.touch()

    def get_composition_strategy(self) -> CompositionStrategy | None:
        """Get structured composition strategy, or None if legacy string/unset."""
        if isinstance(self.composition_strategy, CompositionStrategy):
            return self.composition_strategy
        return None

    def has_structured_composition(self) -> bool:
        """True if composition_strategy is a structured CompositionStrategy object."""
        return isinstance(self.composition_strategy, CompositionStrategy)
