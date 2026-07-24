"""Structured LLM output for Vision Engine visual concept briefs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VisualConceptBriefDraft(BaseModel):
    title: str = Field(min_length=1)
    composition_intent: str = Field(min_length=1)
    atmosphere: str = ""
    diagram_intent: str = ""
    image_type: str = "concept_sketch"
    style_preset: str = "soft_atmosphere"
    subject: str = Field(min_length=1)
    elements: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
