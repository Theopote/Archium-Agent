"""Specialty narrative plans — cultural / renovation / reference style persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents.cultural_narrative_planner import CulturalNarrativePlanner
from archium.agents.reference_style_profiler import ReferenceStyleProfiler
from archium.agents.renovation_issue_planner import RenovationIssueMapPlanner
from archium.application._helpers import build_project_context, build_retrieval_query_from_brief
from archium.application.artifact_history_service import (
    CulturalNarrativeHistoryService,
    ReferenceStyleProfileHistoryService,
    RenovationIssueMapHistoryService,
)
from archium.application.artifact_lineage import (
    apply_cultural_narrative_lineage,
    apply_reference_style_profile_lineage,
    apply_renovation_issue_map_lineage,
)
from archium.application.reference_style_service import (
    build_reference_style_context,
    has_reference_style_documents,
)
from archium.config.settings import Settings, get_settings
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.enums import RevisionSource
from archium.domain.presentation import PresentationBrief
from archium.domain.reference_style import ReferenceStyleProfile
from archium.domain.renovation_issue import RenovationIssueMap
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.base import LLMProvider


class CulturalNarrativeService:
    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._projects = ProjectRepository(session)
        self._history = CulturalNarrativeHistoryService(session)
        self._planner = CulturalNarrativePlanner(llm, settings=self._settings)

    def generate(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        *,
        version: int | None = None,
    ) -> CulturalNarrativePlan | None:
        if not self._planner.should_run(brief):
            return None
        previous_plans = self._projects.list_cultural_narratives(project_id)
        previous = previous_plans[0] if previous_plans else None
        if previous is not None:
            self._history.archive_before_regeneration(previous)
        if version is None:
            version = (previous.version + 1) if previous is not None else 1
        project_context = build_project_context(
            self._session,
            project_id,
            query=build_retrieval_query_from_brief(brief),
            settings=self._settings,
        )
        plan = self._planner.propose(
            project_id,
            brief,
            project_context=project_context,
            version=version,
        )
        apply_cultural_narrative_lineage(plan, previous)
        saved = self._projects.save_cultural_narrative(plan)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)
        self._projects.set_current_cultural_narrative(saved.project_id, saved.id)
        return saved


class RenovationIssueMapService:
    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._projects = ProjectRepository(session)
        self._history = RenovationIssueMapHistoryService(session)
        self._planner = RenovationIssueMapPlanner(llm, settings=self._settings)

    def generate(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        *,
        version: int | None = None,
    ) -> RenovationIssueMap | None:
        if not self._planner.should_run(brief):
            return None
        previous_maps = self._projects.list_renovation_issue_maps(project_id)
        previous = previous_maps[0] if previous_maps else None
        if previous is not None:
            self._history.archive_before_regeneration(previous)
        if version is None:
            version = (previous.version + 1) if previous is not None else 1
        project_context = build_project_context(
            self._session,
            project_id,
            query=build_retrieval_query_from_brief(brief),
            settings=self._settings,
        )
        plan = self._planner.propose(
            project_id,
            brief,
            project_context=project_context,
            version=version,
        )
        apply_renovation_issue_map_lineage(plan, previous)
        saved = self._projects.save_renovation_issue_map(plan)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)
        self._projects.set_current_renovation_issue_map(saved.project_id, saved.id)
        return saved


class ReferenceStyleProfileService:
    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._projects = ProjectRepository(session)
        self._history = ReferenceStyleProfileHistoryService(session)
        self._profiler = ReferenceStyleProfiler(llm, settings=self._settings)

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
        profile = self._profiler.propose(
            project_id,
            brief,
            reference_context=reference_context,
            source_document_ids=source_document_ids,
            version=version,
        )
        apply_reference_style_profile_lineage(profile, previous)
        saved = self._projects.save_reference_style_profile(profile)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)
        self._projects.set_current_reference_style_profile(saved.project_id, saved.id)
        return saved
