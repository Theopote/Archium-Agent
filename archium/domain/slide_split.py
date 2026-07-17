"""Slide split planning models for narrative-aware page breaks."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from archium.domain._base import DomainModel
from archium.domain.slide import SlideSpec

GENERIC_CONTINUATION_MESSAGE = "本页延续上一页内容，详见下列要点。"


class SlideSplitPlan(DomainModel):
    """Plan to split one slide into multiple narrative-coherent pages.

    Split execution must only proceed after structural validation passes.
    """

    reason: str = Field(min_length=1)
    source_slide_id: UUID
    new_slides: list[SlideSpec] = Field(min_length=2)
    citation_mapping: dict[str, UUID] = Field(default_factory=dict)
    asset_mapping: dict[int, UUID] = Field(default_factory=dict)
    requires_human_approval: bool = False
    validation_issues: list[str] = Field(default_factory=list)
    planning_source: str = Field(default="rule")

    @field_validator("new_slides")
    @classmethod
    def _source_slide_is_first(cls, slides: list[SlideSpec]) -> list[SlideSpec]:
        return slides

    @property
    def updated_source(self) -> SlideSpec:
        return self.new_slides[0]

    @property
    def continuation_slides(self) -> list[SlideSpec]:
        return self.new_slides[1:]

    @property
    def primary_continuation(self) -> SlideSpec:
        return self.new_slides[1]
