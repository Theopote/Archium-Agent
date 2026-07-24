"""Intent evolution — how design intent shifts over the project life."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class IntentEvolutionKind(StrEnum):
    SEED = "seed"
    AI_UNDERSTANDING = "ai_understanding"
    RESEARCH = "research"
    DIRECTION_SELECTED = "direction_selected"
    MISSION_COMMIT = "mission_commit"
    EVIDENCE = "evidence"


class IntentEvolutionEvent(DomainModel):
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    kind: IntentEvolutionKind
    summary: str = Field(min_length=1)
    design_intent_snapshot: dict[str, object] | None = None


class IntentEvolution(DomainModel):
    """Ordered log of intent shifts (Project-level)."""

    events: list[IntentEvolutionEvent] = Field(default_factory=list)

    def append(
        self,
        kind: IntentEvolutionKind,
        summary: str,
        *,
        design_intent_snapshot: dict[str, object] | None = None,
    ) -> IntentEvolution:
        events = list(self.events)
        events.append(
            IntentEvolutionEvent(
                kind=kind,
                summary=summary.strip(),
                design_intent_snapshot=design_intent_snapshot,
            )
        )
        return IntentEvolution(events=events)

    def latest_summary(self) -> str | None:
        if not self.events:
            return None
        return self.events[-1].summary
