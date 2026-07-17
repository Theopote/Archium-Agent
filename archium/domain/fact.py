"""Project fact extraction model."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.citation import Citation
from archium.domain.enums import VerificationStatus

FactValue = str | int | float | bool | list[Any] | dict[str, Any]


class ProjectFact(IdentifiedModel, TimestampedModel):
    """A structured fact about a project, with provenance and verification state."""

    project_id: UUID
    key: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=500)
    value: FactValue
    unit: str | None = None
    category: str = Field(default="general", min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.EXTRACTED
    source_citations: list[Citation] = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def _normalize_key(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "_")

    @property
    def is_confirmed(self) -> bool:
        return self.verification_status == VerificationStatus.USER_CONFIRMED

    @property
    def is_inferred(self) -> bool:
        return self.verification_status == VerificationStatus.INFERRED

    def confirm(self) -> None:
        """Mark the fact as user-confirmed."""
        self.verification_status = VerificationStatus.USER_CONFIRMED
        self.touch()

    def reject(self) -> None:
        """Mark the fact as rejected."""
        self.verification_status = VerificationStatus.REJECTED
        self.touch()

    def mark_inferred(self) -> None:
        """Mark the fact as inferred rather than directly extracted."""
        self.verification_status = VerificationStatus.INFERRED
        self.touch()

    def mark_conflicted(self) -> None:
        """Mark the fact as having conflicting sources."""
        self.verification_status = VerificationStatus.CONFLICTED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)
