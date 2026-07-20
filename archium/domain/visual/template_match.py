"""Template layout matching result models."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class TemplateLayoutCandidate(DomainModel):
    """A ranked template page suggested for a SlideSpec."""

    template_id: UUID
    template_name: str = ""
    layout_id: str = Field(min_length=1)
    layout_name: str = ""
    page_index: int = Field(ge=0, default=0)
    page_type: str = ""
    score: float = Field(ge=0.0)
    reasons: list[str] = Field(default_factory=list)
    design_system_id: UUID | None = None
