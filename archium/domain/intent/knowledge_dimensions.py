"""Multi-axis knowledge dimensions — not a single maturity score."""

from __future__ import annotations

from pydantic import Field, model_validator

from archium.domain._base import DomainModel


class KnowledgeDimensions(DomainModel):
    """Architectural cognition axes.

    A temple project may score low on information_completeness yet high on
    design_intent_clarity — that must not collapse into one "maturity" float.
    """

    information_completeness: float = Field(ge=0.0, le=1.0, default=0.0)
    design_intent_clarity: float = Field(ge=0.0, le=1.0, default=0.0)
    evidence_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    constraint_understanding: float = Field(ge=0.0, le=1.0, default=0.0)
    user_alignment: float = Field(ge=0.0, le=1.0, default=0.0)
    research_need: float = Field(ge=0.0, le=1.0, default=0.0)

    @model_validator(mode="after")
    def _fill_research_need_if_unset(self) -> KnowledgeDimensions:
        derived = derive_research_need(
            information_completeness=self.information_completeness,
            evidence_confidence=self.evidence_confidence,
            constraint_understanding=self.constraint_understanding,
        )
        has_signal = (
            self.information_completeness > 0.0
            or self.design_intent_clarity > 0.0
            or self.evidence_confidence > 0.0
            or self.constraint_understanding > 0.0
            or self.user_alignment > 0.0
        )
        if self.research_need <= 0.0 and has_signal:
            object.__setattr__(self, "research_need", derived)
        return self

    def display_score(self) -> float:
        """Compat aggregate — NOT a maturity verdict; prefer reading axes."""
        return (
            self.information_completeness * 0.25
            + self.design_intent_clarity * 0.25
            + self.evidence_confidence * 0.2
            + self.constraint_understanding * 0.15
            + self.user_alignment * 0.15
        )

    def summary_bits(self, *, limit: int = 3) -> list[str]:
        pairs = [
            ("资料", self.information_completeness),
            ("意图", self.design_intent_clarity),
            ("证据", self.evidence_confidence),
            ("约束", self.constraint_understanding),
            ("对齐", self.user_alignment),
            ("研究需求", self.research_need),
        ]
        # Surface extremes first (high intent / high research / low info)
        ranked = sorted(
            pairs,
            key=lambda item: abs(item[1] - 0.5),
            reverse=True,
        )
        return [f"{label} {int(round(score * 100))}%" for label, score in ranked[:limit]]

    @classmethod
    def from_legacy(
        cls,
        *,
        completeness_score: float = 0.0,
        evidence_ratio: float = 0.0,
        assumption_ratio: float = 1.0,
    ) -> KnowledgeDimensions:
        """Bridge pre-dimension KnowledgeState JSON."""
        info = _clamp(completeness_score)
        evidence = _clamp(evidence_ratio)
        constraint = _clamp(1.0 - assumption_ratio)
        # Legacy had no intent axis — use mid-high when sparse-but-described
        intent = _clamp(max(0.25, completeness_score * 0.5 + (1.0 - assumption_ratio) * 0.35))
        alignment = _clamp(0.35 + intent * 0.25)
        research = derive_research_need(
            information_completeness=info,
            evidence_confidence=evidence,
            constraint_understanding=constraint,
        )
        return cls(
            information_completeness=info,
            design_intent_clarity=intent,
            evidence_confidence=evidence,
            constraint_understanding=constraint,
            user_alignment=alignment,
            research_need=research,
        )


def derive_research_need(
    *,
    information_completeness: float,
    evidence_confidence: float,
    constraint_understanding: float,
) -> float:
    coverage = min(
        _clamp(information_completeness),
        _clamp(evidence_confidence),
        _clamp(constraint_understanding),
    )
    return _clamp(1.0 - coverage)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
