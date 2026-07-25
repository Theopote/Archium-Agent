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


class KnowledgeDimensionsDraft(BaseModel):
    """Multi-axis cognition — do not collapse into one maturity score."""

    information_completeness: float = Field(ge=0.0, le=1.0, default=0.2)
    design_intent_clarity: float = Field(ge=0.0, le=1.0, default=0.3)
    evidence_confidence: float = Field(ge=0.0, le=1.0, default=0.1)
    constraint_understanding: float = Field(ge=0.0, le=1.0, default=0.15)
    user_alignment: float = Field(ge=0.0, le=1.0, default=0.3)
    research_need: float = Field(ge=0.0, le=1.0, default=0.5)


class ContextAssessmentDraft(BaseModel):
    completeness_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.3,
        description="Compat aggregate only; prefer dimensions.*",
    )
    maturity_stage: str = "concept_formation"
    evidence_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    assumption_ratio: float = Field(ge=0.0, le=1.0, default=0.8)
    dimensions: KnowledgeDimensionsDraft | None = None
    known: dict[str, str] = Field(default_factory=dict)
    unknown: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    suggested_origin_mode: str = "concept_exploration"
    understanding_summary: str = ""
    actions: list[NextBestActionDraft] = Field(default_factory=list)
