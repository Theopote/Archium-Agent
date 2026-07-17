"""Revision history for Brief and Storyline artifacts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.artifact_snapshots import brief_to_snapshot, storyline_to_snapshot
from archium.application.revision_service import RevisionService
from archium.application.slide_diff import change_source_label
from archium.domain.enums import RevisionEntityType, SlideChangeSource
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
        change_source: SlideChangeSource,
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
            SlideChangeSource.REGENERATION,
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
        change_source: SlideChangeSource,
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
            SlideChangeSource.REGENERATION,
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
