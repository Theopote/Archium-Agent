"""Presentation review issue model."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.enums import ReviewCategory, ReviewSeverity, ReviewStatus


class ReviewIssue(IdentifiedModel, TimestampedModel):
    """A quality or consistency issue found during presentation review."""

    presentation_id: UUID
    slide_id: UUID | None = None
    category: ReviewCategory
    severity: ReviewSeverity
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1)
    suggestion: str | None = None
    auto_fixable: bool = False
    status: ReviewStatus = ReviewStatus.OPEN

    def resolve(self) -> None:
        self.status = ReviewStatus.RESOLVED
        self.touch()

    def dismiss(self) -> None:
        self.status = ReviewStatus.DISMISSED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)
