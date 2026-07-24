"""Structured LLM output for concept direction drafts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConceptDirectionDraft(BaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    theme: str = ""
    spatial_idea: str = ""
    experience_focus: str = ""
    differentiator: str = ""
    open_questions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class ConceptDirectionBatchDraft(BaseModel):
    directions: list[ConceptDirectionDraft] = Field(default_factory=list)
