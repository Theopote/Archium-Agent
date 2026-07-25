"""Design History Graph helpers over IntentEvolution edges.

IntentEvolution events are already graph edges:
Trigger → Old Intent → New Intent → Reason → Evidence

This module queries / formats them without inventing a parallel store.
"""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.concept_direction import ConceptDirection
from archium.domain.intent.intent_evolution import (
    IntentEvolution,
    IntentEvolutionEvent,
    IntentEvolutionKind,
)
from archium.domain.project_mission import ProjectMission


@dataclass(frozen=True)
class DesignHistoryEdge:
    """View model for one Design History edge."""

    kind: IntentEvolutionKind
    trigger: str
    previous: str
    new: str
    reason: str
    evidence: tuple[str, ...]
    display_line: str
    at_iso: str

    @classmethod
    def from_event(cls, event: IntentEvolutionEvent) -> DesignHistoryEdge:
        return cls(
            kind=event.kind,
            trigger=(event.trigger or "").strip(),
            previous=(event.previous_summary or "").strip(),
            new=(event.new_summary or "").strip(),
            reason=(event.reason or "").strip(),
            evidence=tuple(event.evidence_refs or ()),
            display_line=event.display_line(),
            at_iso=event.at.isoformat(),
        )


def iter_design_history_edges(
    evolution: IntentEvolution | None,
    *,
    require_shift: bool = True,
) -> list[DesignHistoryEdge]:
    """Return Design History edges oldest → newest.

    When ``require_shift`` is True, only events with old/new/reason/evidence
    (structured graph fields) are included; pure status summaries are skipped.
    """
    if evolution is None:
        return []
    edges: list[DesignHistoryEdge] = []
    for event in evolution.events:
        if require_shift and not event.has_history_edge():
            continue
        edges.append(DesignHistoryEdge.from_event(event))
    return edges


def intent_label_from_mission(mission: ProjectMission) -> str:
    """Stable short label for Mission intent (theme or title)."""
    if mission.design_intent is not None and mission.design_intent.theme.strip():
        return mission.design_intent.theme.strip()[:120]
    if mission.task_statement.strip():
        return mission.task_statement.strip().splitlines()[0][:120]
    return (mission.title or "").strip()[:120]


def intent_label_from_direction(direction: ConceptDirection) -> str:
    """Stable short label for a concept direction."""
    if direction.theme.strip():
        return direction.theme.strip()[:120]
    return (direction.title or "").strip()[:120]


def format_shift_line(
    *,
    previous: str | None,
    new: str | None,
    reason: str | None,
) -> str:
    """Same phrasing as IntentEvolutionEvent.display_line for ad-hoc writers."""
    prev = (previous or "").strip()
    nxt = (new or "").strip()
    why = (reason or "").strip()
    if prev and nxt and why:
        return f"因为{why}，从「{prev}」调整为「{nxt}」"
    if prev and nxt:
        return f"从「{prev}」调整为「{nxt}」"
    if nxt and why:
        return f"因为{why}，调整为「{nxt}」"
    return nxt or why or ""
