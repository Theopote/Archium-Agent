"""Boundary helpers: dynamic cognition lives in KnowledgeState, not Mission.

ProjectMission may still carry generation-time ``key_unknowns`` / ``confidence``
as deprecated snapshots for compat. Runtime reads should prefer KS / ProjectContext.

Boundary:
- ProjectMission — stable task definition (problem / questions / intent / constraints)
- ProjectContext / KnowledgeState — live cognition (unknowns / confidence / claims)
"""

from __future__ import annotations

from uuid import UUID

from archium.application.unit_of_work import SessionLike, session_of
from archium.domain.context.project_context import ProjectContext
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.project_mission import ProjectMission

# Fields that must not be treated as live cognition after first generation.
MISSION_COGNITION_SNAPSHOT_FIELDS = frozenset({"key_unknowns", "confidence"})


def cognition_unknown_texts(
    *,
    knowledge_state: KnowledgeState | None = None,
    project_context: ProjectContext | None = None,
    mission: ProjectMission | None = None,
) -> list[str]:
    """Open unknowns for display / Brief — KS authoritative, Mission fallback only."""
    state = knowledge_state
    if state is None and project_context is not None:
        state = project_context.knowledge_state
    if state is not None:
        if state.open_unknowns:
            return [
                gap.description.strip()
                for gap in state.open_unknowns
                if gap.description and gap.description.strip()
            ]
        merged = list(state.unknown or []) + list(state.missing_information or [])
        seen: set[str] = set()
        out: list[str] = []
        for item in merged:
            key = item.strip()
            if not key:
                continue
            norm = key.casefold()
            if norm in seen:
                continue
            seen.add(norm)
            out.append(key)
        if out:
            return out
    if mission is not None:
        return [item.strip() for item in mission.key_unknowns if item and item.strip()]
    return []


def cognition_confidence(
    *,
    project_context: ProjectContext | None = None,
    knowledge_state: KnowledgeState | None = None,
    mission: ProjectMission | None = None,
) -> float:
    """Runtime confidence — ProjectContext/KS evidence, Mission generation snapshot last."""
    if project_context is not None:
        return max(0.0, min(1.0, float(project_context.confidence)))
    if knowledge_state is not None:
        dims = knowledge_state.effective_dimensions()
        return max(0.0, min(1.0, float(dims.evidence_confidence)))
    if mission is not None:
        return max(0.0, min(1.0, float(mission.confidence)))
    return 0.0


def load_project_knowledge_state(
    session: SessionLike,
    project_id: UUID,
) -> KnowledgeState | None:
    """Load live KnowledgeState for Mission-adjacent readers."""
    session = session_of(session)
    from archium.infrastructure.database.repositories import ProjectRepository

    project = ProjectRepository(session).get_by_id(project_id)
    if project is None:
        return None
    return project.knowledge_state


def strip_cognition_snapshot_fields(payload: dict) -> dict:
    """Remove deprecated Mission cognition keys from a patch / dump dict."""
    cleaned = dict(payload)
    for key in MISSION_COGNITION_SNAPSHOT_FIELDS:
        cleaned.pop(key, None)
    return cleaned
