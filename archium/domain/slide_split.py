"""Slide split planning models for narrative-aware page breaks."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from archium.domain._base import DomainModel, new_uuid
from archium.domain.slide import SlideSpec

GENERIC_CONTINUATION_MESSAGE = "本页延续上一页内容，详见下列要点。"


def citation_key(document_id: UUID, chunk_id: UUID | None, index: int) -> str:
    if chunk_id is not None:
        return str(chunk_id)
    return f"{document_id}:{index}"


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
    narrative_reason: str | None = None

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


class SlideSplitPagePreview(DomainModel):
    """One page summary for before/after split confirmation UI."""

    title: str = ""
    message: str = ""
    key_points: list[str] = Field(default_factory=list)


class SlideSplitProposal(DomainModel):
    """Reviewable split proposal — confirm before mutating the deck.

    OVERLOADED capacity → propose → before/after → user accept → apply.
    """

    proposal_id: UUID = Field(default_factory=new_uuid)
    source_slide_id: UUID
    plan: SlideSplitPlan
    before: SlideSplitPagePreview
    after: list[SlideSplitPagePreview] = Field(default_factory=list)
    status: Literal["draft", "accepted", "rejected"] = "draft"
    capacity_status: str = ""
