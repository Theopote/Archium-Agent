"""Deck-level narrative arc and per-section narrative position."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.enums import NarrativeStage

# Canonical progression for regression / coverage checks.
NARRATIVE_STAGE_ORDER: tuple[NarrativeStage, ...] = (
    NarrativeStage.CONTEXT,
    NarrativeStage.PROBLEM,
    NarrativeStage.EVIDENCE,
    NarrativeStage.TENSION,
    NarrativeStage.STRATEGY,
    NarrativeStage.RESOLUTION,
    NarrativeStage.DECISION,
)

_CATEGORY_TO_STAGE: dict[str, NarrativeStage] = {
    "intro": NarrativeStage.CONTEXT,
    "context": NarrativeStage.CONTEXT,
    "background": NarrativeStage.CONTEXT,
    "heritage": NarrativeStage.CONTEXT,
    "culture": NarrativeStage.CONTEXT,
    "problem": NarrativeStage.PROBLEM,
    "issue": NarrativeStage.PROBLEM,
    "现状": NarrativeStage.PROBLEM,
    "evidence": NarrativeStage.EVIDENCE,
    "tension": NarrativeStage.TENSION,
    "strategy": NarrativeStage.STRATEGY,
    "approach": NarrativeStage.STRATEGY,
    "concept": NarrativeStage.STRATEGY,
    "technical": NarrativeStage.STRATEGY,
    "implementation": NarrativeStage.STRATEGY,
    "策略": NarrativeStage.STRATEGY,
    "resolution": NarrativeStage.RESOLUTION,
    "decision": NarrativeStage.DECISION,
    "closing": NarrativeStage.DECISION,
    "conclusion": NarrativeStage.DECISION,
    "summary": NarrativeStage.DECISION,
    "结语": NarrativeStage.DECISION,
    "总结": NarrativeStage.DECISION,
}


class NarrativeArc(DomainModel):
    """Deck-level argument skeleton — fixed before page generation."""

    opening_context: str = Field(min_length=1)
    central_problem: str = Field(min_length=1)
    tension_building: list[str] = Field(default_factory=list)
    turning_point: str = Field(min_length=1)
    proposed_resolution: str = Field(min_length=1)
    final_decision: str | None = None


class NarrativePosition(DomainModel):
    """Where an outline section sits on the deck narrative arc."""

    stage: NarrativeStage
    advances_from_previous: str = Field(default="", max_length=1000)
    prepares_for_next: str = Field(default="", max_length=1000)


def narrative_stage_rank(stage: NarrativeStage) -> int:
    try:
        return NARRATIVE_STAGE_ORDER.index(stage)
    except ValueError:
        return -1


def infer_narrative_stage(category: str) -> NarrativeStage | None:
    """Map legacy outline category strings onto NarrativeStage when position is absent."""
    key = category.strip().casefold()
    if key in _CATEGORY_TO_STAGE:
        return _CATEGORY_TO_STAGE[key]
    # Non-casefolded Chinese keys
    raw = category.strip()
    return _CATEGORY_TO_STAGE.get(raw)
