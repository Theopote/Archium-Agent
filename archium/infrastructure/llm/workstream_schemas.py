"""Structured LLM output schemas for workstream planning."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkstreamDraft(BaseModel):
    """One recommended workstream in a planning draft."""

    title: str
    workstream_type: str = "other"
    objective: str
    questions: list[str] = Field(default_factory=list)
    inputs_required: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    dependency_indices: list[int] = Field(default_factory=list)
    blocking_gap_indices: list[int] = Field(default_factory=list)
    priority: str = "medium"
    effort_level: str = "medium"
    recommended: bool = True
    reason: str = ""


class WorkstreamPlanDraft(BaseModel):
    """LLM output for dynamic workstream planning."""

    workstreams: list[WorkstreamDraft] = Field(default_factory=list)
    planning_notes: str = ""
