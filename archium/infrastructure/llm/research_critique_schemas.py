"""LLM drafts for research finding critique."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchCritiqueIssueDraft(BaseModel):
    text: str = Field(min_length=1)
    kind: str = "other"
    severity: str = "medium"


class ResearchCritiqueDraft(BaseModel):
    validity: float = Field(default=0.5, ge=0.0, le=1.0)
    design_relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    verdict: str = "caution"
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    issues: list[ResearchCritiqueIssueDraft] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
