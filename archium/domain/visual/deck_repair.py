"""Actionable deck-level repair suggestions derived from Deck QA findings."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class DeckRepairSuggestion(DomainModel):
    """User-triggered repair action mapped from a Deck QA finding."""

    rule_code: str = Field(min_length=1)
    slide_id: UUID
    intent: str = Field(min_length=1)
    label: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    params: dict[str, object] = Field(default_factory=dict)
