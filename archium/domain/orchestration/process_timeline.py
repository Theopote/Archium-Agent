"""Orchestration process timeline — design-process checkpoint semantics.

Append-only log on orchestration WorkflowRun.state (not a parallel Domain store).
Links stages / gates / router decisions to IntentEvolution kinds by reference.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from archium.domain._base import DomainModel


class ProcessTimelineEvent(DomainModel):
    """One durable orchestration process event (WorkflowCheckpoint-lite)."""

    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    kind: str = Field(
        default="stage",
        description="stage | gate | replan | reflection | complete | failed",
    )
    stage: str = ""
    status: str = ""
    label: str = ""
    summary: str = ""
    human_gate: dict[str, object] | None = None
    decision_router: dict[str, object] | None = None
    child_workflow_run_id: str | None = None
    intent_evolution_kind: str | None = Field(
        default=None,
        description="Optional IntentEvolutionKind.value when this event also wrote evolution.",
    )
    artifact_refs: list[str] = Field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def display_line(self) -> str:
        bits = [self.label or self.kind]
        if self.stage:
            bits.append(self.stage)
        if self.status:
            bits.append(self.status)
        if self.summary.strip():
            bits.append(self.summary.strip()[:120])
        return " · ".join(bits)


PROCESS_TIMELINE_KEY = "process_timeline"
_DEFAULT_MAX = 48


def append_process_timeline_event(
    state: dict[str, Any],
    event: ProcessTimelineEvent | dict[str, object],
    *,
    max_entries: int = _DEFAULT_MAX,
) -> dict[str, Any]:
    """Append to ``state['process_timeline']``; returns updated state dict."""
    payload = event.as_dict() if isinstance(event, ProcessTimelineEvent) else dict(event)
    log = list(state.get(PROCESS_TIMELINE_KEY) or [])
    # Deduplicate consecutive identical stage+status+kind
    if log:
        last = log[-1]
        if (
            last.get("kind") == payload.get("kind")
            and last.get("stage") == payload.get("stage")
            and last.get("status") == payload.get("status")
            and last.get("summary") == payload.get("summary")
        ):
            return state
    log.append(payload)
    return {**state, PROCESS_TIMELINE_KEY: log[-max_entries:]}


def list_process_timeline(
    state: dict[str, Any] | None,
    *,
    limit: int = 24,
) -> list[ProcessTimelineEvent]:
    if not state:
        return []
    raw = list(state.get(PROCESS_TIMELINE_KEY) or [])
    events: list[ProcessTimelineEvent] = []
    for item in raw[-limit:]:
        if not isinstance(item, dict):
            continue
        try:
            events.append(ProcessTimelineEvent.model_validate(item))
        except Exception:
            continue
    return events
