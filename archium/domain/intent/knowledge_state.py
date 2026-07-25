"""Project knowledge state — continuous multi-axis cognition, not binary materials."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from archium.domain._base import DomainModel
from archium.domain.intent.context_assessment_reason import ContextAssessmentReason
from archium.domain.intent.knowledge_claim import KnowledgeClaimRef, KnowledgeUnknownRef
from archium.domain.intent.knowledge_dimensions import KnowledgeDimensions


class KnowledgeMaturityStage(StrEnum):
    CONCEPT_FORMATION = "concept_formation"
    DESIGN_ANALYSIS = "design_analysis"
    TECHNICAL_PRESENTATION = "technical_presentation"


class KnowledgeState(DomainModel):
    """Cognitive index: multi-axis dimensions + claim pointers.

    Authoritative bodies live in ProjectFact / ProjectKnowledgeItem.
    ``completeness_score`` is a display/compat aggregate — do not treat it as
    the sole maturity signal (see ``dimensions``).
    """

    completeness_score: float = Field(ge=0.0, le=1.0, default=0.0)
    maturity_stage: KnowledgeMaturityStage = KnowledgeMaturityStage.CONCEPT_FORMATION
    evidence_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    assumption_ratio: float = Field(ge=0.0, le=1.0, default=1.0)
    dimensions: KnowledgeDimensions = Field(default_factory=KnowledgeDimensions)
    known: dict[str, str] = Field(default_factory=dict)
    unknown: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    claims: list[KnowledgeClaimRef] = Field(default_factory=list)
    open_unknowns: list[KnowledgeUnknownRef] = Field(default_factory=list)
    lifecycle_stage: str = ""
    recommended_workflow: str = ""
    primary_page_key: str = ""
    fact_count: int = Field(default=0, ge=0)
    source_count: int = Field(default=0, ge=0)
    knowledge_item_count: int = Field(default=0, ge=0)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = Field(default="initial", max_length=40)
    cognition_stale: bool = Field(
        default=False,
        description="True when last best-effort LLM reassess failed; claim index may still be fresh.",
    )
    assessment_reasons: list[ContextAssessmentReason] = Field(
        default_factory=list,
        description="Last ContextAssessment reasoning trace (why NBA / stage).",
    )

    @model_validator(mode="after")
    def _ensure_dimensions(self) -> KnowledgeState:
        dims = self.dimensions
        blank = (
            dims.information_completeness <= 0.0
            and dims.design_intent_clarity <= 0.0
            and dims.evidence_confidence <= 0.0
            and dims.constraint_understanding <= 0.0
            and dims.user_alignment <= 0.0
        )
        if blank and (
            self.completeness_score > 0.0
            or self.evidence_ratio > 0.0
            or self.assumption_ratio < 1.0
        ):
            object.__setattr__(
                self,
                "dimensions",
                KnowledgeDimensions.from_legacy(
                    completeness_score=self.completeness_score,
                    evidence_ratio=self.evidence_ratio,
                    assumption_ratio=self.assumption_ratio,
                ),
            )
        return self

    def effective_dimensions(self) -> KnowledgeDimensions:
        dims = self.dimensions
        blank = (
            dims.information_completeness <= 0.0
            and dims.design_intent_clarity <= 0.0
            and dims.evidence_confidence <= 0.0
        )
        if blank:
            return KnowledgeDimensions.from_legacy(
                completeness_score=self.completeness_score,
                evidence_ratio=self.evidence_ratio,
                assumption_ratio=self.assumption_ratio,
            )
        return dims

    def with_synced_legacy_scores(self) -> KnowledgeState:
        """Refresh compat floats from dimensions (call after assess)."""
        dims = self.effective_dimensions()
        return self.model_copy(
            update={
                "dimensions": dims,
                "completeness_score": dims.display_score(),
                "evidence_ratio": dims.evidence_confidence,
                "assumption_ratio": max(0.0, 1.0 - dims.evidence_confidence),
            }
        )

    def summary_line(self) -> str:
        dims = self.effective_dimensions()
        bits = " · ".join(dims.summary_bits(limit=3))
        stage = {
            KnowledgeMaturityStage.CONCEPT_FORMATION: "概念形成",
            KnowledgeMaturityStage.DESIGN_ANALYSIS: "设计分析",
            KnowledgeMaturityStage.TECHNICAL_PRESENTATION: "技术汇报",
        }.get(self.maturity_stage, self.maturity_stage.value)
        return f"{bits} · 阶段：{stage}"
