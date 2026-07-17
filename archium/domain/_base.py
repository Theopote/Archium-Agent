"""Shared base types for domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class DomainModel(BaseModel):
    """Base Pydantic model for Archium domain entities."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )


class TimestampedModel(DomainModel):
    """Mixin for entities with creation and update timestamps."""

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def touch(self) -> None:
        """Update the ``updated_at`` timestamp."""
        self.updated_at = utc_now()


class VersionedModel(DomainModel):
    """Mixin for versioned artifacts."""

    version: int = Field(default=1, ge=1)


class IdentifiedModel(DomainModel):
    """Mixin for entities with a UUID primary key."""

    id: UUID = Field(default_factory=uuid4)


def new_uuid() -> UUID:
    """Generate a new UUID."""
    return uuid4()


def model_to_dict(model: BaseModel, *, exclude_none: bool = False) -> dict[str, Any]:
    """Serialize a domain model to a JSON-compatible dict."""
    return model.model_dump(mode="json", exclude_none=exclude_none)
