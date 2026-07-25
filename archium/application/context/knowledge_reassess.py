"""Best-effort KnowledgeState refresh after product lifecycle events."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.context.types import ContextAssessment
from archium.config.settings import Settings, get_settings
from archium.infrastructure.llm.base import LLMProvider
from archium.logging import get_logger

logger = get_logger(__name__, operation="knowledge_reassess")


def best_effort_reassess_knowledge(
    session: Session,
    project_id: UUID,
    *,
    llm: LLMProvider | None = None,
    settings: Settings | None = None,
    reason: str = "",
) -> ContextAssessment | None:
    """Refresh ProjectContext / KnowledgeState without failing the caller.

    Used after clarification continue, mission approval, direction select/commit,
    uploads, and fact confirmation so completeness stays event-driven.
    """
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
        return None
