"""Multi-axis knowledge vector — not a single maturity score.

``KnowledgeDimensions`` is the Knowledge Vector (v1). Prefer reading axes /
``as_vector()`` over ``completeness_score``. ``design_readiness`` is derived —
never treat it as an independent LLM truth score.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from archium.domain._base import DomainModel


class KnowledgeDimensions(DomainModel):
    """Architectural cognition vector (facts / intent / evidence / …).

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

    # --- Vector aliases (Knowledge Vector vocabulary) ---

    @property
    def facts(self) -> float:
        return self.information_completeness

    @property
    def intent(self) -> float:
        return self.design_intent_clarity

    @property
    def evidence(self) -> float:
        return self.evidence_confidence

    @property
    def constraints(self) -> float:
        return self.constraint_understanding

    @property
    def context(self) -> float:
        """Project / user context understanding (alignment-weighted)."""
        return _clamp(self.user_alignment * 0.7 + self.constraint_understanding * 0.3)

    @property
    def design_readiness(self) -> float:
        """Derived readiness to advance design — not an LLM free score.

        Intent-led projects (clear concept, sparse drawings) can still be
        moderately ready; weak intent always suppresses readiness.
        """
        intent = self.design_intent_clarity
        facts = self.information_completeness
        material_floor = max(facts, intent * 0.7)
        constraint_floor = self.constraint_understanding * 0.5 + 0.5
        evidence_floor = self.evidence_confidence * 0.4 + 0.6
        alignment_floor = self.user_alignment * 0.35 + 0.65
        return _clamp(
            min(intent, material_floor, constraint_floor, evidence_floor, alignment_floor)
        )

    def as_vector(self) -> dict[str, float]:
        """Canonical Knowledge Vector view for routing / UI."""
        return {
            "facts": self.facts,
            "intent": self.intent,
            "context": float(self.context),
            "constraints": self.constraints,
            "evidence": self.evidence,
            "design_readiness": float(self.design_readiness),
            "research_need": self.research_need,
        }

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
            ("资料", self.facts),
            ("意图", self.intent),
            ("证据", self.evidence),
            ("约束", self.constraints),
            ("语境", float(self.context)),
            ("设计就绪", float(self.design_readiness)),
            ("研究需求", self.research_need),
        ]
        ranked = sorted(
            pairs,
            key=lambda item: abs(item[1] - 0.5),
            reverse=True,
        )
        return [f"{label} {int(round(score * 100))}%" for label, score in ranked[:limit]]

    def vector_bars(self) -> list[tuple[str, float]]:
        """Ordered axes for UI progress bars."""
        v = self.as_vector()
        return [
            ("资料 facts", v["facts"]),
            ("意图 intent", v["intent"]),
            ("语境 context", v["context"]),
            ("约束 constraints", v["constraints"]),
            ("证据 evidence", v["evidence"]),
            ("设计就绪 readiness", v["design_readiness"]),
            ("研究需求 research", v["research_need"]),
        ]

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
        intent = _clamp(
            max(0.25, completeness_score * 0.5 + (1.0 - assumption_ratio) * 0.35)
        )
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


# Public alias — Knowledge Vector is KnowledgeDimensions (do not fork a second model).
KnowledgeVector = KnowledgeDimensions


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
