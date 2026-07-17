"""Generate structured presentation briefs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import (
    brief_from_draft,
    build_project_context,
    build_request_context,
)
from archium.application.presentation_models import PresentationRequest
from archium.domain.presentation import PresentationBrief
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import BriefDraft
from archium.prompts.presentation_brief import BRIEF_SYSTEM_PROMPT, build_brief_user_prompt


class BriefBuilder:
    """Build and persist PresentationBrief artifacts."""

    def __init__(self, session: Session, llm: LLMProvider) -> None:
        self._session = session
        self._llm = llm
        self._presentations = PresentationRepository(session)

    def generate(
        self,
        project_id: UUID,
        presentation_id: UUID,
        request: PresentationRequest,
        *,
        version: int | None = None,
    ) -> PresentationBrief:
        if version is None:
            version = self._next_brief_version(presentation_id)

        project_context = build_project_context(self._session, project_id)
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
        saved = self._presentations.save_brief(brief)

        from archium.domain.enums import PresentationStatus

        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is not None:
            presentation.current_brief_id = saved.id
            if presentation.status == PresentationStatus.DRAFT:
                presentation.status = PresentationStatus.IN_PROGRESS
            self._presentations.update_presentation(presentation)

        return saved

    def _next_brief_version(self, presentation_id: UUID) -> int:
        briefs = self._presentations.list_briefs(presentation_id)
        if not briefs:
            return 1
        return max(item.version for item in briefs) + 1
