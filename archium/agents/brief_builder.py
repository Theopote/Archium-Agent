"""Generate structured presentation briefs — LLM proposal only (no Session)."""

from __future__ import annotations

from uuid import UUID

from archium.application._helpers import brief_from_draft, build_request_context
from archium.application.presentation_models import PresentationRequest
from archium.config.settings import Settings, get_settings
from archium.domain.presentation import PresentationBrief
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import BriefDraft
from archium.prompts.presentation_brief import BRIEF_SYSTEM_PROMPT, build_brief_user_prompt


class BriefBuilder:
    """Narrative planner: propose a PresentationBrief from context text.

    Does **not** read/write the database. Persistence belongs to ``BriefService``.
    """

    def __init__(
        self,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._llm = llm
        self._settings = settings or get_settings()

    def propose(
        self,
        *,
        project_id: UUID,
        presentation_id: UUID,
        request: PresentationRequest,
        project_context: str,
        version: int = 1,
    ) -> PresentationBrief:
        """Return an unsaved Brief (caller applies lineage + persist)."""
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
        return brief_from_draft(
            draft,
            project_id=project_id,
            presentation_id=presentation_id,
            version=version,
        )
