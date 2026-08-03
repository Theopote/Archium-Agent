"""Best-effort KnowledgeState refresh after product lifecycle events."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.application.context.types import ContextAssessment
from archium.config.settings import Settings, get_settings
from archium.infrastructure.llm.base import LLMProvider
from archium.logging import get_logger

logger = get_logger(__name__, operation="knowledge_reassess")

class ReassessMode(StrEnum):
    """How aggressively to refresh cognition after a product event."""

    INDEX = "index"  # deterministic claim index only
    FULL = "full"  # LLM reassess (+ index fallback on failure)

# Evidence deltas that only need claim/gap re-index — not a full LLM rejudge.
_INDEX_REASONS = frozenset(
    {
        "fact_confirmed",
        "fact_rejected",
        "knowledge_item_confirmed",
        "knowledge_item_rejected",
        "research_step",
    }
)

def classify_reassess_mode(reason: str | None) -> ReassessMode:
    """Map lifecycle reason → index-only vs full LLM reassess."""
    key = (reason or "").strip().lower()
    if key in _INDEX_REASONS:
        return ReassessMode.INDEX
    return ReassessMode.FULL

def best_effort_reassess_knowledge(
    session: SessionLike,
    project_id: UUID,
    *,
    llm: LLMProvider | None = None,
    settings: Settings | None = None,
    reason: str = "",
    mode: ReassessMode | str | None = None,
) -> ContextAssessment | None:
    """Refresh ProjectContext / KnowledgeState without failing the caller.

    Small evidence events (e.g. fact_confirmed) use deterministic claim-index
    refresh. Larger lifecycle events run full LLM reassess; on failure fall
    back to claim-index and mark cognition_stale.
    """
    session = session_of(session)
    resolved_mode = _resolve_mode(mode, reason)
    if resolved_mode == ReassessMode.INDEX:
        return _best_effort_index_refresh(session, project_id, reason=reason)

    return _best_effort_full_reassess(
        session,
        project_id,
        llm=llm,
        settings=settings,
        reason=reason,
    )

def _resolve_mode(
    mode: ReassessMode | str | None,
    reason: str,
) -> ReassessMode:
    if mode is None:
        return classify_reassess_mode(reason)
    if isinstance(mode, ReassessMode):
        return mode
    raw = str(mode).strip().lower()
    if raw in {ReassessMode.INDEX.value, "index_only", "incremental"}:
        return ReassessMode.INDEX
    return ReassessMode.FULL

def _best_effort_index_refresh(
    session: SessionLike,
    project_id: UUID,
    *,
    reason: str = "",
) -> ContextAssessment | None:
    session = session_of(session)
    try:
        from archium.application.context.knowledge_claim_index import (
            refresh_claim_index_only,
        )
        from archium.application.context.project_context_builder import (
            build_project_context,
        )
        from archium.application.context.types import ContextAssessment as Assessment

        state = refresh_claim_index_only(
            session,
            project_id,
            mark_stale=False,
            history_reason=reason or "index_refresh",
        )
        if state is None:
            return None
        ctx = build_project_context(session, project_id)
        actions = list(ctx.next_actions) if ctx is not None else []
        summary = (ctx.understanding_summary if ctx is not None else "") or ""
        origin = (
            ctx.suggested_origin_mode
            if ctx is not None
            else _default_origin()
        )
        assessment = Assessment(
            knowledge_state=ctx.knowledge_state if ctx is not None else state,
            actions=actions,
            understanding_summary=summary,
            suggested_origin_mode=origin,
            project_context=ctx,
        )
        logger.info(
            "KnowledgeState claim index refreshed (%s, project=%s, claims=%d)",
            reason or "index",
            project_id,
            len(assessment.knowledge_state.claims),
        )
        return assessment
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Best-effort claim-index refresh skipped (%s): %s",
            reason or "unspecified",
            exc,
        )
        return None

def _best_effort_full_reassess(
    session: SessionLike,
    project_id: UUID,
    *,
    llm: LLMProvider | None = None,
    settings: Settings | None = None,
    reason: str = "",
) -> ContextAssessment | None:
    session = session_of(session)
    try:
        from archium.application.context.context_analyzer import ContextAnalyzer
        from archium.infrastructure.llm.factory import create_llm_provider

        resolved_settings = settings or get_settings()
        provider = llm or create_llm_provider(resolved_settings)
        assessment = ContextAnalyzer(
            session,
            provider,
            settings=resolved_settings,
        ).reassess(project_id, history_reason=reason or "refresh")
        if reason:
            logger.info(
                "KnowledgeState reassessed after %s (project=%s, completeness=%.2f)",
                reason,
                project_id,
                assessment.knowledge_state.completeness_score,
            )
        return assessment
    except Exception as exc:  # noqa: BLE001 — never block primary product actions
        logger.warning(
            "Best-effort KnowledgeState reassess skipped (%s): %s",
            reason or "unspecified",
            exc,
        )
        try:
            from archium.application.context.knowledge_claim_index import (
                refresh_claim_index_only,
            )

            refreshed = refresh_claim_index_only(
                session,
                project_id,
                mark_stale=True,
                history_reason=reason or "reassess_failed",
            )
            if refreshed is not None:
                logger.info(
                    "Claim index refreshed after failed reassess (%s, project=%s)",
                    reason or "unspecified",
                    project_id,
                )
        except Exception as index_exc:  # noqa: BLE001
            logger.warning(
                "Claim-index fallback also failed (%s): %s",
                reason or "unspecified",
                index_exc,
            )
        return None

def _default_origin() -> Any:
    from archium.domain.enums import ProjectOriginMode

    return ProjectOriginMode.CONCEPT_EXPLORATION
