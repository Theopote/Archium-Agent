"""User preference and memory models."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel


class UserPreference(IdentifiedModel, TimestampedModel):
    """Persisted user preferences for presentation generation defaults."""

    key: str = Field(min_length=1, max_length=200)
    value: Any
    project_id: UUID | None = None
    description: str | None = None

    def touch(self) -> None:
        TimestampedModel.touch(self)
