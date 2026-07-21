"""Reference slide matching models (WP I — Phase 6 precursor)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class DeckContext(DomainModel):
    """Neighbour and deck-level signals for reference page selection."""

    section_id: str = ""
    section_title: str = ""
    section_index: int = Field(default=0, ge=0)
    planned_page_index: int = Field(default=0, ge=0)
    previous_slide_summary: str = ""
    next_slide_intent: str = ""
    previous_content_type: str = ""
    next_content_type: str = ""
    used_layout_ids: list[str] = Field(default_factory=list)
    used_schema_ids: list[str] = Field(default_factory=list)
    used_representative_slide_ids: list[str] = Field(default_factory=list)


class ReferenceSlideCandidate(DomainModel):
    """Ranked reference page for template-editing generation."""

    template_id: UUID
    layout_id: str = ""
    layout_name: str = ""
    schema_id: str = ""
    representative_slide_id: str = ""
    page_index: int = Field(default=0, ge=0)
    page_type: str = ""
    score: float = Field(ge=0.0, le=1.0)
    rank: int = Field(default=1, ge=1)
    candidate_kind: Literal["recommended", "alternate", "free_composition"] = "alternate"
    reasons: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
