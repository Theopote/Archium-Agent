"""Project knowledge state — continuous completeness, not binary materials."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class KnowledgeMaturityStage(StrEnum):
    CONCEPT_FORMATION = "concept_formation"
    DESIGN_ANALYSIS = "design_analysis"
    TECHNICAL_PRESENTATION = "technical_presentation"


class KnowledgeState(DomainModel):
    """Snapshot of what the project knows / does not know right now."""

    completeness_score: float = Field(ge=0.0, le=1.0, default=0.0)
    maturity_stage: KnowledgeMaturityStage = KnowledgeMaturityStage.CONCEPT_FORMATION
    evidence_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    assumption_ratio: float = Field(ge=0.0, le=1.0, default=1.0)
    known: dict[str, str] = Field(default_factory=dict)
    unknown: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    lifecycle_stage: str = ""
    recommended_workflow: str = ""
    primary_page_key: str = ""
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = Field(default="initial", max_length=40)

    def summary_line(self) -> str:
        pct = int(round(self.completeness_score * 100))
        stage = {
            KnowledgeMaturityStage.CONCEPT_FORMATION: "概念形成",
            KnowledgeMaturityStage.DESIGN_ANALYSIS: "设计分析",
            KnowledgeMaturityStage.TECHNICAL_PRESENTATION: "技术汇报",
        }.get(self.maturity_stage, self.maturity_stage.value)
        return f"知识完整度约 {pct}% · 阶段：{stage}"
