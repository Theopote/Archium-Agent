"""Structured LLM output for autonomous research synthesis."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchSourceDraft(BaseModel):
    title: str = Field(min_length=1)
    url: str | None = None
    note: str = ""


class ResearchFindingDraft(BaseModel):
    topic: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    key_points: list[str] = Field(default_factory=list)
    suggested_sources: list[ResearchSourceDraft] = Field(default_factory=list)
    relevance: str = ""


class AutonomousResearchDraft(BaseModel):
    findings: list[ResearchFindingDraft] = Field(default_factory=list)
