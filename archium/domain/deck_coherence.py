"""Deck-level narrative coherence QA — argument, repetition, section closure."""

from __future__ import annotations

from pydantic import Field, computed_field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import LayoutIssueSeverity

DECK_DUPLICATE_MESSAGE = "DECK.DUPLICATE_MESSAGE"
DECK_DUPLICATE_KEY_POINT = "DECK.DUPLICATE_KEY_POINT"
DECK_STRATEGY_WITHOUT_PROBLEM = "DECK.STRATEGY_WITHOUT_PROBLEM"
DECK_CLOSING_WITHOUT_DECISION = "DECK.CLOSING_WITHOUT_DECISION"
DECK_WEAK_SECTION_EVIDENCE = "DECK.WEAK_SECTION_EVIDENCE"
DECK_REPEATED_CHAPTER_MESSAGE = "DECK.REPEATED_CHAPTER_MESSAGE"
DECK_NO_ADVANCEMENT = "DECK.NO_ADVANCEMENT"
DECK_STRATEGY_UNANCHORED = "DECK.STRATEGY_UNANCHORED"
DECK_STAGE_REGRESSION = "DECK.STAGE_REGRESSION"
DECK_RESOLUTION_UNSUPPORTED = "DECK.RESOLUTION_UNSUPPORTED"


class DeckCoherenceFinding(DomainModel):
    rule_code: str = Field(min_length=1)
    severity: LayoutIssueSeverity = LayoutIssueSeverity.WARNING
    message: str = Field(min_length=1)
    suggestion: str | None = None
    slide_ids: list[str] = Field(default_factory=list)
    section_ids: list[str] = Field(default_factory=list)


class DeckCoherenceReport(DomainModel):
    method: str = "deck_coherence_v1"
    slide_count: int = Field(default=0, ge=0)
    findings: list[DeckCoherenceFinding] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def finding_codes(self) -> list[str]:
        return sorted({item.rule_code for item in self.findings})
