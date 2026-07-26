"""Presentation Intelligence — product-facing Visual seat summary (v0.3).

Not a new Agent. Composes Style Preset + ArtDirection + Deck rhythm +
Page Director into one investor/designer-readable brief.
"""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel

PRESENTATION_INTELLIGENCE_SCHEMA = "presentation_intelligence_v1"


class PresentationIntelligenceBrief(DomainModel):
    """What a designer/investor should read before opening the PPT."""

    schema_version: str = PRESENTATION_INTELLIGENCE_SCHEMA
    case_id: str | None = None
    style_preset_id: str = Field(min_length=1)
    project_personality: str = Field(min_length=1, max_length=120)
    personality_blurb: str = Field(default="", max_length=400)
    narrative_logic: str = Field(default="", max_length=40)
    emotion_level: str = Field(default="", max_length=20)
    image_role: str = Field(default="", max_length=20)
    content_policy_summary: str = Field(default="", max_length=200)
    audience_summary: str = Field(default="", max_length=200)
    story_rhythm: str = Field(default="", max_length=400)
    emotional_curve: list[str] = Field(default_factory=list)
    climax_titles: list[str] = Field(default_factory=list)
    density_min: float | None = None
    density_max: float | None = None
    page_direction_hits: int = Field(default=0, ge=0)
    situation_rules_fired: list[str] = Field(default_factory=list)
    first_impression_checks: list[str] = Field(default_factory=list)
    demo_tour_titles: list[str] = Field(default_factory=list)
