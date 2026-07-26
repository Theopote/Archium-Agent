"""Project event log service — emit + project from IntentEvolution / process timeline."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.domain.intent.intent_evolution import IntentEvolution, IntentEvolutionKind
from archium.domain.orchestration.process_timeline import (
    PROCESS_TIMELINE_KEY,
    ProcessTimelineEvent,
    list_process_timeline,
)
from archium.domain.project_event import (
    ProjectEvent,
    ProjectEventActor,
    ProjectEventType,
)
from archium.infrastructure.database.repositories import ProjectEventRepository

_INTENT_TO_EVENT: dict[IntentEvolutionKind, ProjectEventType] = {
    IntentEvolutionKind.SEED: ProjectEventType.CONTEXT_UPDATED,
    IntentEvolutionKind.AI_UNDERSTANDING: ProjectEventType.CONTEXT_UPDATED,
    IntentEvolutionKind.RESEARCH: ProjectEventType.RESEARCH_COMPLETED,
    IntentEvolutionKind.DIRECTION_SELECTED: ProjectEventType.CONCEPT_SELECTED,
    IntentEvolutionKind.DESIGN_CRITIQUE: ProjectEventType.DESIGN_CRITIQUE,
    IntentEvolutionKind.MISSION_COMMIT: ProjectEventType.MISSION_CHANGED,
    IntentEvolutionKind.MISSION_APPROVED: ProjectEventType.MISSION_CHANGED,
    IntentEvolutionKind.EVIDENCE: ProjectEventType.CONTEXT_UPDATED,
    IntentEvolutionKind.VISUAL_FEEDBACK: ProjectEventType.VISUAL_FEEDBACK,
    IntentEvolutionKind.DESIGN_DECISION: ProjectEventType.DESIGN_DECISION,
    IntentEvolutionKind.REFLECTION: ProjectEventType.REFLECTION,
}


def _fingerprint(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class ProjectEventService:
    """Append-only project memory; projections are idempotent via dedupe_key."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = ProjectEventRepository(session)

    def emit(
        self,
        project_id: UUID,
        event_type: ProjectEventType,
        summary: str,
        *,
        actor: ProjectEventActor = ProjectEventActor.SYSTEM,
        payload: dict[str, Any] | None = None,
        dedupe_key: str = "",
        source: str = "explicit",
        at: datetime | None = None,
    ) -> ProjectEvent | None:
        text = (summary or "").strip()
        if not text:
            return None
        key = (dedupe_key or "").strip() or f"emit:{uuid4()}"
        if dedupe_key and self._repo.exists_dedupe(project_id, key):
            return None
        event = ProjectEvent(
            project_id=project_id,
            event_type=event_type,
            actor=actor,
            summary=text[:800],
            payload=dict(payload or {}),
            dedupe_key=key[:200],
            source=source[:80],
        )
        if at is not None:
            event = event.model_copy(update={"at": at})
        return self._repo.create(event)

    def sync_from_intent_evolution(
        self,
        project_id: UUID,
        evolution: IntentEvolution | None,
    ) -> int:
        """Project new IntentEvolution events into project_events. Returns insert count."""
        if evolution is None or not evolution.events:
            return 0
        inserted = 0
        for index, item in enumerate(evolution.events):
            kind = item.kind
            event_type = _INTENT_TO_EVENT.get(kind, ProjectEventType.INTENT_CHANGED)
            at = item.at
            key = f"intent:{kind.value}:{at.isoformat()}:{_fingerprint(item.summary, index)}"
            payload: dict[str, Any] = {
                "intent_kind": kind.value,
                "display": item.display_line(),
            }
            if item.trigger:
                payload["trigger"] = item.trigger
            if item.reason:
                payload["reason"] = item.reason
            created = self.emit(
                project_id,
                event_type,
                item.display_line() or item.summary,
                actor=ProjectEventActor.AI,
                payload=payload,
                dedupe_key=key,
                source="intent_evolution",
                at=at,
            )
            if created is not None:
                inserted += 1
        return inserted

    def sync_from_workflow_state(
        self,
        project_id: UUID,
        workflow_run_id: UUID,
        state: dict[str, Any] | None,
    ) -> int:
        """Project process_timeline entries into project_events."""
        if not state or PROCESS_TIMELINE_KEY not in state:
            return 0
        inserted = 0
        for index, raw in enumerate(list_process_timeline(state)):
            try:
                event = (
                    raw
                    if isinstance(raw, ProcessTimelineEvent)
                    else ProcessTimelineEvent.model_validate(raw)
                )
            except Exception:
                continue
            key = (
                f"process:{workflow_run_id}:{event.at.isoformat()}:"
                f"{event.kind}:{event.stage}:{_fingerprint(event.summary, index)}"
            )
            created = self.emit(
                project_id,
                ProjectEventType.PROCESS_CHECKPOINT,
                event.display_line(),
                actor=ProjectEventActor.SYSTEM,
                payload={
                    "process_kind": event.kind,
                    "stage": event.stage,
                    "status": event.status,
                    "workflow_run_id": str(workflow_run_id),
                    "intent_evolution_kind": event.intent_evolution_kind,
                },
                dedupe_key=key,
                source="process_timeline",
                at=event.at,
            )
            if created is not None:
                inserted += 1
        return inserted

    def list_for_project(
        self,
        project_id: UUID,
        *,
        limit: int = 40,
        event_types: list[ProjectEventType] | None = None,
    ) -> list[ProjectEvent]:
        return self._repo.list_for_project(
            project_id, limit=limit, event_types=event_types
        )
