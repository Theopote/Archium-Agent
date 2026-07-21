"""Presentation outline plan — editable structure before SlideSpec generation."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import Field, model_validator

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import ApprovalStatus, OutlineAudienceMode
from archium.domain.narrative_arc import NarrativePosition
from archium.domain.slide_asset_binding import SlideAssetBinding
from archium.domain.slide_intent import SlideIntent

OUTLINE_LOGICAL_KEY = "presentation-outline"


class OutlineSection(DomainModel):
    """A planned chapter/section in the presentation outline."""

    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1)
    key_message: str = Field(min_length=1)
    estimated_slide_count: int = Field(default=1, ge=0)
    evidence_requirements: list[str] = Field(default_factory=list)
    required_assets: list[str] = Field(default_factory=list)
    required: bool = True
    expanded: bool = True
    order: int = Field(default=0, ge=0)
    category: str = Field(default="general", min_length=1)
    narrative_position: NarrativePosition | None = None


class OutlinePlan(IdentifiedModel, VersionedModel, TimestampedModel):
    """User-editable presentation structure confirmed before page-level SlideSpec."""

    presentation_id: UUID
    lineage_id: UUID = Field(default_factory=uuid4)
    logical_key: str = Field(default=OUTLINE_LOGICAL_KEY, max_length=200)
    # Optional link to the research manuscript that seeded this outline.
    manuscript_id: UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    thesis: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    target_slide_count: int = Field(default=20, ge=1, le=200)
    audience_mode: OutlineAudienceMode = OutlineAudienceMode.GOVERNMENT
    sections: list[OutlineSection] = Field(default_factory=list)
    # Independent per-page intent cards (page_instructions), keyed by order.
    page_intents: list[SlideIntent] = Field(default_factory=list)
    # Explicit page→asset bindings (page_materials); applied before auto-match.
    page_asset_bindings: list[SlideAssetBinding] = Field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT

    @model_validator(mode="after")
    def _validate_section_order(self) -> OutlinePlan:
        if not self.sections:
            return self
        orders = [section.order for section in self.sections]
        if len(orders) != len(set(orders)):
            raise ValueError("outline section order values must be unique")
        return self

    @property
    def estimated_slide_total(self) -> int:
        return sum(
            section.estimated_slide_count
            for section in self.sections
            if section.expanded
        )

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
