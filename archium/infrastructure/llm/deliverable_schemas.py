"""Structured LLM output schemas for deliverable planning."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlannedDeliverableDraft(BaseModel):
    """One planned deliverable in a draft plan."""

    id: str
    title: str
    deliverable_type: str = "other"
    purpose: str
    audience: str = ""
    content_scope: list[str] = Field(default_factory=list)
    source_workstream_indices: list[int] = Field(default_factory=list)
    recommendation: str = "optional"  # required | optional | not_recommended
    format: str = "markdown"
    expected_length: str | None = None
    notes: str | None = None
    decision_served: str = ""


class DeliverablePlanDraft(BaseModel):
    """LLM output for dynamic deliverable planning."""

    deliverables: list[PlannedDeliverableDraft] = Field(default_factory=list)
    planning_notes: str = ""
