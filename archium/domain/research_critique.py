"""Research critique — challenge research findings before they harden as design knowledge.

Critic seat artifact: read-only. Does not rewrite findings or KnowledgeState.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel, TimestampedModel, utc_now


class ResearchCritiqueVerdict(StrEnum):
    ACCEPT = "accept"
    CAUTION = "caution"
    WEAK = "weak"


class ResearchCritiqueIssueKind(StrEnum):
    BACKGROUND_ONLY = "background_only"
    WEAK_CITATION = "weak_citation"
    OVER_ANALOGY = "over_analogy"
    LOW_DESIGN_RELEVANCE = "low_design_relevance"
    MISSING_STRUCTURE = "missing_structure"
    OTHER = "other"


class ResearchCritiqueIssue(DomainModel):
    text: str = Field(min_length=1, max_length=500)
    kind: ResearchCritiqueIssueKind = ResearchCritiqueIssueKind.OTHER
    severity: str = Field(default="medium", max_length=20)


class ResearchCritiqueReport(TimestampedModel):
    """Independent critique of research outputs (validity + design relevance)."""

    project_id: UUID | None = None
    mission_id: UUID | None = None
    validity: float = Field(default=0.5, ge=0.0, le=1.0)
    design_relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    verdict: ResearchCritiqueVerdict = ResearchCritiqueVerdict.CAUTION
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    issues: list[ResearchCritiqueIssue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    source: str = Field(default="rules", max_length=40)  # rules | llm | mixed
    item_count: int = 0

    def touch_completed(self) -> None:
        self.updated_at = utc_now()

    @property
    def is_weak(self) -> bool:
        return self.verdict == ResearchCritiqueVerdict.WEAK

    def display_warnings(self) -> list[str]:
        lines = [w for w in self.warnings if str(w).strip()]
        if self.summary.strip() and self.summary.strip() not in lines:
            lines.insert(0, self.summary.strip())
        for issue in self.issues[:4]:
            lines.append(f"{issue.kind.value}: {issue.text}")
        return lines

    def as_dict(self) -> dict[str, object]:
        return {
            "project_id": str(self.project_id) if self.project_id else None,
            "mission_id": str(self.mission_id) if self.mission_id else None,
            "validity": self.validity,
            "design_relevance": self.design_relevance,
            "verdict": self.verdict.value,
            "summary": self.summary,
            "warnings": list(self.warnings),
            "issues": [item.model_dump() for item in self.issues],
            "strengths": list(self.strengths),
            "source": self.source,
            "item_count": self.item_count,
        }
