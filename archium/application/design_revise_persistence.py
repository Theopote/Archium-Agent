"""Durable design Ask / critique hydrate (Topic 07 L2 / APP-026 / APP-027)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.domain.intent.intent_evolution import IntentEvolution
from archium.infrastructure.database.repositories import ProjectRepository

_MAX_OFFER_CHARS = 120_000


def persist_pending_design_revise(
    session: SessionLike,
    project_id: UUID,
    offer: dict[str, Any],
) -> None:
    """Stamp Ask offer onto Project.intent_evolution (survives refresh)."""
    session = session_of(session)
    project = ProjectRepository(session).get_by_id(project_id)
    if project is None:
        return
    payload = dict(offer)
    # Soft size guard — keep JSON column healthy
    raw = str(payload)
    if len(raw) > _MAX_OFFER_CHARS:
        payload = {
            "direction_id": payload.get("direction_id"),
            "project_id": payload.get("project_id"),
            "mode": payload.get("mode") or "ask",
            "diff_lines": list(payload.get("diff_lines") or [])[:10],
            "critique": payload.get("critique"),
            "truncated": True,
        }
    evo = project.intent_evolution or IntentEvolution()
    project.intent_evolution = evo.with_pending_design_revise(payload)
    project.touch()
    ProjectRepository(session).update(project)


def clear_pending_design_revise(session: SessionLike, project_id: UUID) -> None:
    session = session_of(session)
    project = ProjectRepository(session).get_by_id(project_id)
    if project is None:
        return
    evo = project.intent_evolution or IntentEvolution()
    if evo.pending_design_revise is None:
        return
    project.intent_evolution = evo.clear_pending_design_revise()
    project.touch()
    ProjectRepository(session).update(project)


def load_pending_design_revise(
    session: SessionLike,
    project_id: UUID,
) -> dict[str, Any] | None:
    session = session_of(session)
    project = ProjectRepository(session).get_by_id(project_id)
    if project is None:
        return None
    evo = project.intent_evolution
    if evo is None or not isinstance(evo.pending_design_revise, dict):
        return None
    pending = dict(evo.pending_design_revise)
    if not pending.get("direction_id"):
        return None
    return pending


def load_latest_design_critique_report(
    session: SessionLike,
    project_id: UUID,
) -> dict[str, Any] | None:
    """Hydrate DesignCritiqueReport-shaped dict from IntentEvolution or pending Ask."""
    session = session_of(session)
    project = ProjectRepository(session).get_by_id(project_id)
    if project is None:
        return None
    evo = project.intent_evolution
    if evo is None:
        return None
    pending = evo.pending_design_revise
    if isinstance(pending, dict):
        critique = pending.get("critique")
        if isinstance(critique, dict) and critique.get("verdict"):
            return dict(critique)
    snap = evo.latest_design_critique_snapshot()
    return snap


def design_critique_resume_page(report: dict[str, Any] | None) -> str | None:
    """NBA page when critique is caution/reject (back to design loop)."""
    if not isinstance(report, dict):
        return None
    verdict = str(report.get("verdict") or "").strip().lower()
    if verdict not in {"caution", "reject"}:
        return None
    return "concept-exploration"
