"""LLM structured output for architectural design critique."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DesignCritiqueItemDraft(BaseModel):
    text: str = Field(min_length=1)
    challenge: str = "why"
    severity: str = "suggestion"


class DesignCritiqueDraft(BaseModel):
    verdict: str = "caution"
    summary: str = ""
    strengths: list[DesignCritiqueItemDraft] = Field(default_factory=list)
    weaknesses: list[DesignCritiqueItemDraft] = Field(default_factory=list)
    missing_evidence: list[DesignCritiqueItemDraft] = Field(default_factory=list)
    alternative_directions: list[DesignCritiqueItemDraft] = Field(default_factory=list)
    form_only_risk: bool = False
