"""Structured LLM output for context intelligence assessment."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NextBestActionDraft(BaseModel):
    action: str = Field(
        description=(
            "research | ask | explore_directions | upload_materials | "
            "generate_mission | open_mission"
        )
    )
    reason: str = ""
    question: str | None = None
    priority: int = 0


class ContextAssessmentDraft(BaseModel):
    completeness_score: float = Field(ge=0.0, le=1.0, default=0.3)
    maturity_stage: str = "concept_formation"
    evidence_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    assumption_ratio: float = Field(ge=0.0, le=1.0, default=0.8)
    known: dict[str, str] = Field(default_factory=dict)
    unknown: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    suggested_origin_mode: str = "concept_exploration"
    understanding_summary: str = ""
    actions: list[NextBestActionDraft] = Field(default_factory=list)
