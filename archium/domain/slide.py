"""Slide specification and visual requirement models."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from archium.domain._base import DomainModel, IdentifiedModel, VersionedModel
from archium.domain.citation import Citation
from archium.domain.enums import SlideStatus, SlideType, VisualType


class VisualRequirement(DomainModel):
    """Visual asset requirement for a slide."""

    type: VisualType
    description: str = Field(min_length=1)
    preferred_asset_ids: list[UUID] = Field(default_factory=list)
    processing_instructions: list[str] = Field(default_factory=list)
    required: bool = True


class SlideSpec(IdentifiedModel, VersionedModel):
    """Specification for a single presentation slide."""

    presentation_id: UUID
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
