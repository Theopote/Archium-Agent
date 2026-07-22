"""TemplateUsageBrief — human/Agent-readable design contract for induced templates."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel


class TemplateUsageBrief(DomainModel):
    """Structured theme/usage contract derived after Template Induction.

    Markdown rendering is the human/Agent surface; this model is the JSON twin.
    """

    template_id: str = Field(min_length=1)
    template_name: str = Field(min_length=1)
    source_filename: str = ""

    brand_traits: list[str] = Field(default_factory=list)
    title_behavior: str = ""
    typography_hierarchy: list[str] = Field(default_factory=list)
    page_margins: dict[str, float] = Field(default_factory=dict)
    content_density: str = ""
    image_treatment: str = ""
    drawing_treatment: str = ""
    page_number_position: str = ""
    repeated_decorations: list[str] = Field(default_factory=list)
    forbidden_patterns: list[str] = Field(default_factory=list)

    palette: list[str] = Field(default_factory=list)
    fonts: list[str] = Field(default_factory=list)
    motion_principles: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
