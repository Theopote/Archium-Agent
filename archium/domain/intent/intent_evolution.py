"""Intent evolution — Design History Graph edges for architectural process.

Each event ideally records:
Trigger → Old Intent → New Intent → Reason → Evidence

Older events may only have ``summary``; format helpers degrade gracefully.
"""

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
    DESIGN_CRITIQUE = "design_critique"
    MISSION_COMMIT = "mission_commit"
    MISSION_APPROVED = "mission_approved"
    EVIDENCE = "evidence"
    VISUAL_FEEDBACK = "visual_feedback"
    DESIGN_DECISION = "design_decision"
    REFLECTION = "reflection"
    DIRECTION_REVISED = "direction_revised"


def _clip(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return text[:limit]


class IntentEvolutionEvent(DomainModel):
    """One intent-shift edge (compat: summary-only events still valid)."""

    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    kind: IntentEvolutionKind
    summary: str = Field(min_length=1)
    design_intent_snapshot: dict[str, object] | None = None
    # Design History Graph fields (optional for backward compatibility)
    trigger: str | None = Field(
        default=None,
        max_length=200,
        description="What prompted the shift (product cue).",
    )
    previous_summary: str | None = Field(
        default=None,
        max_length=400,
        description="Short label for intent before the shift.",
    )
    new_summary: str | None = Field(
        default=None,
        max_length=400,
        description="Short label for intent after the shift.",
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Why the intent changed.",
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Light evidence pointers (statements, titles, URLs).",
    )
    design_decision: dict[str, object] | None = Field(
        default=None,
        description="Optional DesignDecision payload (model_dump).",
    )

    def display_line(self) -> str:
        """Human-readable Design History line; falls back to summary."""
        previous = (self.previous_summary or "").strip()
        new = (self.new_summary or "").strip()
        reason = (self.reason or "").strip()
        if previous and new and reason:
            return f"因为{reason}，从「{previous}」调整为「{new}」"
        if previous and new:
            return f"从「{previous}」调整为「{new}」"
        if new and reason:
            return f"因为{reason}，调整为「{new}」"
        if new:
            return new
        return self.summary.strip()

    def has_history_edge(self) -> bool:
        return bool(
            (self.previous_summary or "").strip()
            or (self.new_summary or "").strip()
            or (self.reason or "").strip()
            or self.evidence_refs
        )


class IntentEvolution(DomainModel):
    """Ordered Design History log of intent shifts (Project-level)."""

    events: list[IntentEvolutionEvent] = Field(default_factory=list)

    def append(
        self,
        kind: IntentEvolutionKind,
        summary: str,
        *,
        design_intent_snapshot: dict[str, object] | None = None,
        trigger: str | None = None,
        previous_summary: str | None = None,
        new_summary: str | None = None,
        reason: str | None = None,
        evidence_refs: list[str] | None = None,
        design_decision: dict[str, object] | None = None,
    ) -> IntentEvolution:
        events = list(self.events)
        event = IntentEvolutionEvent(
            kind=kind,
            summary=summary.strip(),
            design_intent_snapshot=design_intent_snapshot,
            trigger=_clip(trigger, 200),
            previous_summary=_clip(previous_summary, 400),
            new_summary=_clip(new_summary, 400),
            reason=_clip(reason, 500),
            evidence_refs=[
                ref.strip()[:300]
                for ref in (evidence_refs or [])
                if ref and str(ref).strip()
            ][:12],
            design_decision=design_decision,
        )
        if event.previous_summary or event.new_summary or event.reason:
            event = event.model_copy(update={"summary": event.display_line()[:500]})
        events.append(event)
        return IntentEvolution(events=events)

    def latest_summary(self) -> str | None:
        if not self.events:
            return None
        return self.events[-1].display_line()
