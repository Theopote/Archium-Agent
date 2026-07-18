"""Generate structured presentation briefs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import (
    brief_from_draft,
    build_project_context,
    build_request_context,
    build_retrieval_query_from_request,
)
from archium.application.artifact_history_service import BriefHistoryService
from archium.application.artifact_lineage import apply_brief_lineage
from archium.application.presentation_models import PresentationRequest
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource
from archium.domain.presentation import PresentationBrief
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import BriefDraft
from archium.prompts.presentation_brief import BRIEF_SYSTEM_PROMPT, build_brief_user_prompt


class BriefBuilder:
    """Build and persist PresentationBrief artifacts."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._history = BriefHistoryService(session)

    def generate(
        self,
        project_id: UUID,
        presentation_id: UUID,
        request: PresentationRequest,
        *,
        version: int | None = None,
    ) -> PresentationBrief:
        previous_briefs = self._presentations.list_briefs(presentation_id)
        previous = previous_briefs[0] if previous_briefs else None
        if previous is not None:
            self._history.archive_before_regeneration(previous)

        if version is None:
            version = (previous.version + 1) if previous is not None else 1

        project_context = build_project_context(
            self._session,
            project_id,
            query=build_retrieval_query_from_request(request),
            settings=self._settings,
        )
        request_context = build_request_context(request)
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=BRIEF_SYSTEM_PROMPT,
                user_prompt=build_brief_user_prompt(
                    project_context=project_context,
                    request_context=request_context,
                ),
                temperature=0.3,
            ),
            BriefDraft,
        )
        brief = brief_from_draft(
            draft,
            project_id=project_id,
            presentation_id=presentation_id,
            version=version,
        )
        apply_brief_lineage(brief, previous)
        saved = self._presentations.save_brief(brief)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)

        from archium.domain.enums import PresentationStatus

        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is not None:
            presentation.current_brief_id = saved.id
            if presentation.status == PresentationStatus.DRAFT:
                presentation.status = PresentationStatus.IN_PROGRESS
            self._presentations.update_presentation(presentation)

        return saved
