"""Reference style profile — LLM proposal only (no Session)."""

from __future__ import annotations

from uuid import UUID

from archium.agents._helpers import to_json
from archium.application.reference_style_service import (
    profile_fallback_from_brief,
    profile_from_draft,
)
from archium.config.settings import Settings, get_settings
from archium.domain.presentation import PresentationBrief
from archium.domain.reference_style import ReferenceStyleProfile
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import ReferenceStyleProfileDraft
from archium.prompts.reference_style import (
    REFERENCE_STYLE_PROFILE_SYSTEM_PROMPT,
    build_reference_style_profile_user_prompt,
)


class ReferenceStyleProfiler:
    """Narrative planner: propose ReferenceStyleProfile (no DB)."""

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
        project_id: UUID,
        brief: PresentationBrief,
        *,
        reference_context: str,
        source_document_ids: list[UUID],
        version: int = 1,
    ) -> ReferenceStyleProfile:
        if not self._settings.llm_configured:
            return profile_fallback_from_brief(
                brief,
                project_id=project_id,
                source_document_ids=source_document_ids,
                version=version,
            )
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=REFERENCE_STYLE_PROFILE_SYSTEM_PROMPT,
                user_prompt=build_reference_style_profile_user_prompt(
                    reference_context=reference_context,
                    brief_json=to_json(brief),
                ),
                temperature=0.35,
            ),
            ReferenceStyleProfileDraft,
        )
        profile = profile_from_draft(
            draft,
            project_id=project_id,
            source_document_ids=source_document_ids,
            version=version,
        )
        if not profile.style_name.strip():
            profile = profile_fallback_from_brief(
                brief,
                project_id=project_id,
                source_document_ids=source_document_ids,
                version=version,
            )
        return profile
