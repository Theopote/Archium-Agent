"""Concept direction drafts — design iteration branches under one Mission."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.enums import ConceptDirectionStatus


class ConceptDirection(IdentifiedModel, TimestampedModel):
    """One conceptual design direction draft for a mission."""

    project_id: UUID
    mission_id: UUID
    title: str = Field(min_length=1, max_length=200)
    summary: str = ""
    theme: str = ""
    spatial_idea: str = ""
    experience_focus: str = ""
    differentiator: str = ""
    open_questions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    status: ConceptDirectionStatus = ConceptDirectionStatus.DRAFT
    sort_order: int = 0
    source: str = Field(default="generated", max_length=40)

    def select(self) -> None:
        self.status = ConceptDirectionStatus.SELECTED
        self.touch()

    def mark_draft(self) -> None:
        self.status = ConceptDirectionStatus.DRAFT
        self.touch()

    def archive(self) -> None:
        self.status = ConceptDirectionStatus.ARCHIVED
        self.touch()
