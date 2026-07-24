"""Structured LLM output for writing confirmed research back into a mission."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MissionResearchEnrichmentDraft(BaseModel):
    """Partial mission update after absorbing confirmed public research."""

    project_context: str = Field(
        min_length=1,
        description="Updated project_context merging prior context and confirmed research.",
    )
    current_situation: str | None = None
    key_unknowns: list[str] = Field(default_factory=list)
    note: str = ""


class MissionResearchRevisionDraft(BaseModel):
    """Lightweight mission field updates after research is written back."""

    task_statement: str | None = None
    key_unknowns: list[str] = Field(default_factory=list)
    research_questions: list[str] = Field(default_factory=list)
    note: str = ""
