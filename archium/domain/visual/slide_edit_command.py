"""Unified slide edit command envelope for Presentation Studio."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class SlideEditScope(StrEnum):
    VISUAL = "visual"
    CONTENT = "content"


class SlideEditCommand(DomainModel):
    """One user-triggered slide edit routed to visual or content services."""

    slide_id: UUID
    scope: SlideEditScope
    action: str = Field(min_length=1)
    params: dict[str, object] = Field(default_factory=dict)
    text: str | None = None
