"""Structured reasons for Context Intelligence — why this judgment / path."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class AssessmentReasonPolarity(StrEnum):
    SUPPORT = "support"  # supports the recommended path
    BLOCK = "block"  # blocks a heavier path
    NUANCE = "nuance"  # context / trade-off


class AssessmentReasonAxis(StrEnum):
    FACTS = "facts"
    INTENT = "intent"
    CONTEXT = "context"
    CONSTRAINTS = "constraints"
    EVIDENCE = "evidence"
    DESIGN_READINESS = "design_readiness"
    RESEARCH_NEED = "research_need"
    WORKFLOW = "workflow"
    OTHER = "other"


class ContextAssessmentReason(DomainModel):
    """One explainable factor behind a context assessment (not ProjectContext state)."""

    factor: str = Field(min_length=1, max_length=200)
    evidence: str = Field(default="", max_length=500)
    impact: str = Field(default="", max_length=400)
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    polarity: AssessmentReasonPolarity = AssessmentReasonPolarity.NUANCE
    related_axis: AssessmentReasonAxis = AssessmentReasonAxis.OTHER

    def display_line(self) -> str:
        bits = [self.factor]
        if self.evidence.strip():
            bits.append(self.evidence.strip())
        if self.impact.strip():
            bits.append(f"→ {self.impact.strip()}")
        return " · ".join(bits)
