"""Structured LLM output for entry intent classification."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntryIntentDraft(BaseModel):
    orientation: str = Field(
        description="concept_exploration | existing_project | research_programming"
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: str = ""
    suggested_next: str = ""
