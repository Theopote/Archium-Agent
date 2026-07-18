"""Slide specification and visual requirement models."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from archium.domain._base import DomainModel, IdentifiedModel, VersionedModel
from archium.domain.citation import Citation
from archium.domain.enums import SlideStatus, SlideType, VisualType


def build_slide_logical_key(chapter_id: str, order: int) -> str:
    """Build a stable logical key for a slide within a presentation."""
    return f"{chapter_id.strip()}-p{order}"


class VisualRequirement(DomainModel):
    """Visual asset requirement for a slide."""

    type: VisualType
    description: str = Field(min_length=1)
    preferred_asset_ids: list[UUID] = Field(default_factory=list)
    candidate_asset_ids: list[UUID] = Field(default_factory=list)
    match_score: float | None = Field(default=None, ge=0.0, le=1.0)
    confirmed: bool = False
    needs_crop: bool = False
    needs_highlight: bool = False
    processing_instructions: list[str] = Field(default_factory=list)
    required: bool = True

    @property
    def primary_asset_id(self) -> UUID | None:
        return self.preferred_asset_ids[0] if self.preferred_asset_ids else None

    def bound_asset_ids(self) -> list[UUID]:
        """Return unique bound asset IDs (preferred first, then candidates)."""
        seen: set[UUID] = set()
        ordered: list[UUID] = []
        for asset_id in [*self.preferred_asset_ids, *self.candidate_asset_ids]:
            if asset_id in seen:
                continue
            seen.add(asset_id)
            ordered.append(asset_id)
        return ordered


class SlideSpec(IdentifiedModel, VersionedModel):
    """Specification for a single presentation slide."""

    presentation_id: UUID
    lineage_id: UUID = Field(default_factory=uuid4)
    logical_key: str = Field(default="", max_length=200)
    chapter_id: str = Field(min_length=1)
    order: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=500)
    message: str = Field(min_length=1)
    slide_type: SlideType = SlideType.CONTENT
    layout_id: str = Field(default="default", min_length=1)
    key_points: list[str] = Field(default_factory=list)
    visual_requirements: list[VisualRequirement] = Field(default_factory=list)
    source_citations: list[Citation] = Field(default_factory=list)
    speaker_notes: str | None = None
    status: SlideStatus = SlideStatus.PLANNED

    @model_validator(mode="after")
    def _ensure_lineage_defaults(self) -> SlideSpec:
        if not self.logical_key:
            self.logical_key = build_slide_logical_key(self.chapter_id, self.order)
        return self

    @field_validator("message")
    @classmethod
    def _validate_single_core_message(cls, value: str) -> str:
        """Ensure the slide conveys one clear conclusion, not a list of topics."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be empty")
        if stripped.count("。") > 2 or stripped.count(".") > 2:
            raise ValueError("message should express a single core conclusion")
        return stripped

    @field_validator("key_points")
    @classmethod
    def _limit_key_points(cls, value: list[str]) -> list[str]:
        if len(value) > 5:
            raise ValueError("key_points must not exceed 5 items per slide")
        return value

    def mark_planned(self) -> None:
        self.status = SlideStatus.PLANNED

    def approve(self) -> None:
        self.status = SlideStatus.APPROVED

    def mark_needs_revision(self) -> None:
        self.status = SlideStatus.NEEDS_REVISION
