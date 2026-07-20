"""Revision history for Brief and Storyline artifacts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.artifact_snapshots import brief_to_snapshot, storyline_to_snapshot
from archium.domain.outline import OutlinePlan
from archium.application.revision_service import RevisionService
from archium.application.slide_diff import change_source_label
from archium.domain.enums import RevisionEntityType, RevisionSource
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.revision import EntityRevision


class BriefHistoryService:
    """Brief-specific facade over the unified revision service."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._revisions = RevisionService(session)

    def record_snapshot(
        self,
        brief: PresentationBrief,
        change_source: RevisionSource,
        *,
        note: str | None = None,
    ) -> EntityRevision:
        return self._revisions.record(
            entity_type=RevisionEntityType.BRIEF,
            entity_id=brief.id,
            lineage_id=brief.lineage_id,
            presentation_id=brief.presentation_id,
            change_source=change_source,
            snapshot=brief_to_snapshot(brief),
            note=note,
        )

    def archive_before_regeneration(
        self,
        brief: PresentationBrief,
        *,
        note: str = "重新生成前归档",
    ) -> EntityRevision:
        return self.record_snapshot(
            brief,
            RevisionSource.REGENERATION,
            note=note,
        )

    def list_revisions(self, brief_id: UUID) -> list[EntityRevision]:
        brief = self._get_brief(brief_id)
        if brief is None:
            return []
        return self.list_revisions_by_lineage(brief.lineage_id)

    def list_revisions_by_lineage(self, lineage_id: UUID) -> list[EntityRevision]:
        return self._revisions.list_by_lineage(lineage_id)

    def list_presentation_revisions(self, presentation_id: UUID) -> list[EntityRevision]:
        return self._revisions.list_by_presentation(
            presentation_id,
            entity_type=RevisionEntityType.BRIEF,
        )

    @staticmethod
    def revision_label(revision: EntityRevision) -> str:
        title = str(revision.snapshot.get("title", "Brief"))
        source = change_source_label(revision.change_source)
        return f"修订 #{revision.revision_number} · {source} · {title}"

    def _get_brief(self, brief_id: UUID) -> PresentationBrief | None:
        from archium.infrastructure.database.repositories import PresentationRepository

        return PresentationRepository(self._session).get_brief(brief_id)


class StorylineHistoryService:
    """Storyline-specific facade over the unified revision service."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._revisions = RevisionService(session)

    def record_snapshot(
        self,
        storyline: Storyline,
        change_source: RevisionSource,
        *,
        note: str | None = None,
    ) -> EntityRevision:
        return self._revisions.record(
            entity_type=RevisionEntityType.STORYLINE,
            entity_id=storyline.id,
            lineage_id=storyline.lineage_id,
            presentation_id=storyline.presentation_id,
            change_source=change_source,
            snapshot=storyline_to_snapshot(storyline),
            note=note,
        )

    def archive_before_regeneration(
        self,
        storyline: Storyline,
        *,
        note: str = "重新生成前归档",
    ) -> EntityRevision:
        return self.record_snapshot(
            storyline,
            RevisionSource.REGENERATION,
            note=note,
        )

    def list_revisions(self, storyline_id: UUID) -> list[EntityRevision]:
        storyline = self._get_storyline(storyline_id)
        if storyline is None:
            return []
        return self.list_revisions_by_lineage(storyline.lineage_id)

    def list_revisions_by_lineage(self, lineage_id: UUID) -> list[EntityRevision]:
        return self._revisions.list_by_lineage(lineage_id)

    def list_presentation_revisions(self, presentation_id: UUID) -> list[EntityRevision]:
        return self._revisions.list_by_presentation(
            presentation_id,
            entity_type=RevisionEntityType.STORYLINE,
        )

    @staticmethod
    def revision_label(revision: EntityRevision) -> str:
        thesis = str(revision.snapshot.get("thesis", "Storyline"))[:40]
        source = change_source_label(revision.change_source)
        return f"修订 #{revision.revision_number} · {source} · {thesis}"

    def _get_storyline(self, storyline_id: UUID) -> Storyline | None:
        from archium.infrastructure.database.repositories import PresentationRepository

        return PresentationRepository(self._session).get_storyline(storyline_id)


class OutlineHistoryService:
    """Outline-specific facade over the unified revision service."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._revisions = RevisionService(session)

    def record_snapshot(
        self,
        outline: OutlinePlan,
        change_source: RevisionSource,
        *,
        note: str | None = None,
    ) -> EntityRevision:
        from archium.application.artifact_snapshots import outline_to_snapshot
        from archium.domain.outline import OutlinePlan as OutlinePlanModel

        return self._revisions.record(
            entity_type=RevisionEntityType.OUTLINE,
            entity_id=outline.id,
            lineage_id=outline.lineage_id,
            presentation_id=outline.presentation_id,
            change_source=change_source,
            snapshot=outline_to_snapshot(outline),
            note=note,
        )

    def archive_before_regeneration(
        self,
        outline: OutlinePlanModel,
        *,
        note: str = "重新生成前归档",
    ) -> EntityRevision:
        return self.record_snapshot(
            outline,
            RevisionSource.REGENERATION,
            note=note,
        )

    def list_revisions(self, outline_id: UUID) -> list[EntityRevision]:
        outline = self._get_outline(outline_id)
        if outline is None:
            return []
        return self.list_revisions_by_lineage(outline.lineage_id)

    def list_revisions_by_lineage(self, lineage_id: UUID) -> list[EntityRevision]:
        return self._revisions.list_by_lineage(lineage_id)

    def list_presentation_revisions(self, presentation_id: UUID) -> list[EntityRevision]:
        return self._revisions.list_by_presentation(
            presentation_id,
            entity_type=RevisionEntityType.OUTLINE,
        )

    @staticmethod
    def revision_label(revision: EntityRevision) -> str:
        title = str(revision.snapshot.get("title", "Outline"))[:40]
        source = change_source_label(revision.change_source)
        return f"修订 #{revision.revision_number} · {source} · {title}"

    def _get_outline(self, outline_id: UUID):
        from archium.infrastructure.database.repositories import PresentationRepository

        return PresentationRepository(self._session).get_outline(outline_id)


class CulturalNarrativeHistoryService:
    """Cultural narrative facade over the unified revision service."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._revisions = RevisionService(session)

    def record_snapshot(
        self,
        plan: "CulturalNarrativePlan",
        change_source: RevisionSource,
        *,
        note: str | None = None,
    ) -> EntityRevision:
        from archium.application.artifact_snapshots import cultural_narrative_to_snapshot

        return self._revisions.record(
            entity_type=RevisionEntityType.CULTURAL_NARRATIVE,
            entity_id=plan.id,
            lineage_id=plan.lineage_id,
            presentation_id=None,
            change_source=change_source,
            snapshot=cultural_narrative_to_snapshot(plan),
            note=note,
        )

    def archive_before_regeneration(
        self,
        plan: "CulturalNarrativePlan",
        *,
        note: str = "重新生成前归档",
    ) -> EntityRevision:
        return self.record_snapshot(plan, RevisionSource.REGENERATION, note=note)

    def list_revisions(self, plan_id: UUID) -> list[EntityRevision]:
        plan = self._get_plan(plan_id)
        if plan is None:
            return []
        return self._revisions.list_by_lineage(plan.lineage_id)

    @staticmethod
    def revision_label(revision: EntityRevision) -> str:
        story = str(revision.snapshot.get("central_story", "文化叙事"))[:40]
        source = change_source_label(revision.change_source)
        return f"修订 #{revision.revision_number} · {source} · {story}"

    def _get_plan(self, plan_id: UUID):
        from archium.infrastructure.database.repositories import ProjectRepository

        return ProjectRepository(self._session).get_cultural_narrative(plan_id)


class RenovationIssueMapHistoryService:
    """Renovation issue map facade over the unified revision service."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._revisions = RevisionService(session)

    def record_snapshot(
        self,
        plan: "RenovationIssueMap",
        change_source: RevisionSource,
        *,
        note: str | None = None,
    ) -> EntityRevision:
        from archium.application.artifact_snapshots import renovation_issue_map_to_snapshot

        return self._revisions.record(
            entity_type=RevisionEntityType.RENOVATION_ISSUE_MAP,
            entity_id=plan.id,
            lineage_id=plan.lineage_id,
            presentation_id=None,
            change_source=change_source,
            snapshot=renovation_issue_map_to_snapshot(plan),
            note=note,
        )

    def archive_before_regeneration(
        self,
        plan: "RenovationIssueMap",
        *,
        note: str = "重新生成前归档",
    ) -> EntityRevision:
        return self.record_snapshot(plan, RevisionSource.REGENERATION, note=note)

    def list_revisions(self, plan_id: UUID) -> list[EntityRevision]:
        plan = self._get_plan(plan_id)
        if plan is None:
            return []
        return self._revisions.list_by_lineage(plan.lineage_id)

    @staticmethod
    def revision_label(revision: EntityRevision) -> str:
        summary = str(revision.snapshot.get("building_summary", "改造问题图"))[:40]
        source = change_source_label(revision.change_source)
        return f"修订 #{revision.revision_number} · {source} · {summary}"

    def _get_plan(self, plan_id: UUID):
        from archium.infrastructure.database.repositories import ProjectRepository

        return ProjectRepository(self._session).get_renovation_issue_map(plan_id)


class ReferenceStyleProfileHistoryService:
    """Reference style profile facade over the unified revision service."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._revisions = RevisionService(session)

    def record_snapshot(
        self,
        profile: "ReferenceStyleProfile",
        change_source: RevisionSource,
        *,
        note: str | None = None,
    ) -> EntityRevision:
        from archium.application.artifact_snapshots import reference_style_profile_to_snapshot

        return self._revisions.record(
            entity_type=RevisionEntityType.REFERENCE_STYLE_PROFILE,
            entity_id=profile.id,
            lineage_id=profile.lineage_id,
            presentation_id=None,
            change_source=change_source,
            snapshot=reference_style_profile_to_snapshot(profile),
            note=note,
        )

    def archive_before_regeneration(
        self,
        profile: "ReferenceStyleProfile",
        *,
        note: str = "重新生成前归档",
    ) -> EntityRevision:
        return self.record_snapshot(profile, RevisionSource.REGENERATION, note=note)

    def list_revisions(self, profile_id: UUID) -> list[EntityRevision]:
        profile = self._get_profile(profile_id)
        if profile is None:
            return []
        return self._revisions.list_by_lineage(profile.lineage_id)

    @staticmethod
    def revision_label(revision: EntityRevision) -> str:
        name = str(revision.snapshot.get("style_name", "参考风格"))[:40]
        source = change_source_label(revision.change_source)
        return f"修订 #{revision.revision_number} · {source} · {name}"

    def _get_profile(self, profile_id: UUID):
        from archium.infrastructure.database.repositories import ProjectRepository

        return ProjectRepository(self._session).get_reference_style_profile(profile_id)
