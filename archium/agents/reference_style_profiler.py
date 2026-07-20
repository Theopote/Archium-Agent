"""Generate reference style profiles from reference-style documents."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import to_json
from archium.application.artifact_history_service import ReferenceStyleProfileHistoryService
from archium.application.artifact_lineage import apply_reference_style_profile_lineage
from archium.application.reference_style_service import (
    build_reference_style_context,
    has_reference_style_documents,
    profile_fallback_from_brief,
    profile_from_draft,
)
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource
from archium.domain.presentation import PresentationBrief
from archium.domain.reference_style import ReferenceStyleProfile
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import ReferenceStyleProfileDraft
from archium.prompts.reference_style import (
    REFERENCE_STYLE_PROFILE_SYSTEM_PROMPT,
    build_reference_style_profile_user_prompt,
)


class ReferenceStyleProfiler:
    """Extract ReferenceStyleProfile when project has reference-style documents."""

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
        self._projects = ProjectRepository(session)
        self._history = ReferenceStyleProfileHistoryService(session)

    def generate(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        *,
        version: int | None = None,
    ) -> ReferenceStyleProfile | None:
        if not has_reference_style_documents(self._session, project_id):
            return None

        previous_profiles = self._projects.list_reference_style_profiles(project_id)
        previous = previous_profiles[0] if previous_profiles else None
        if previous is not None:
            self._history.archive_before_regeneration(previous)

        if version is None:
            version = (previous.version + 1) if previous is not None else 1

        reference_context, source_document_ids = build_reference_style_context(
            self._session,
            project_id,
        )

        if not self._settings.llm_configured:
            plan = profile_fallback_from_brief(
                brief,
                project_id=project_id,
                source_document_ids=source_document_ids,
                version=version,
            )
            return self._persist(plan, version, previous)

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

        return self._persist(profile, version, previous)

    def _persist(
        self,
        profile: ReferenceStyleProfile,
        version: int,
        previous: ReferenceStyleProfile | None,
    ) -> ReferenceStyleProfile:
        profile.version = version
        apply_reference_style_profile_lineage(profile, previous)
        saved = self._projects.save_reference_style_profile(profile)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)
        self._projects.set_current_reference_style_profile(saved.project_id, saved.id)
        return saved
