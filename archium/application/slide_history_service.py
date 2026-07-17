"""Persist and compare slide revision history."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.slide_diff import (
    change_source_label,
    diff_snapshots,
    slide_to_snapshot,
    snapshot_label,
)
from archium.domain.enums import SlideChangeSource
from archium.domain.slide import SlideSpec
from archium.domain.slide_history import SlideDiffResult, SlideRevision
from archium.exceptions import SlideRevisionNotFoundError
from archium.infrastructure.database.repositories import SlideRevisionRepository


class SlideHistoryService:
    """Record and inspect slide specification revisions."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._revisions = SlideRevisionRepository(session)

    def record_snapshot(
        self,
        slide: SlideSpec,
        change_source: SlideChangeSource,
        *,
        note: str | None = None,
    ) -> SlideRevision:
        revision_number = self._revisions.next_revision_number(slide.id)
        revision = SlideRevision(
            slide_id=slide.id,
            presentation_id=slide.presentation_id,
            revision_number=revision_number,
            change_source=change_source,
            snapshot=slide_to_snapshot(slide),
            note=note,
        )
        return self._revisions.create(revision)

    def archive_slides_before_regeneration(
        self,
        slides: list[SlideSpec],
        *,
        note: str = "重新生成前归档",
    ) -> list[SlideRevision]:
        archived: list[SlideRevision] = []
        for slide in slides:
            archived.append(
                self.record_snapshot(
                    slide,
                    SlideChangeSource.REGENERATION,
                    note=note,
                )
            )
        return archived

    def list_revisions(self, slide_id: UUID) -> list[SlideRevision]:
        return self._revisions.list_by_slide(slide_id)

    def list_presentation_revisions(self, presentation_id: UUID) -> list[SlideRevision]:
        return self._revisions.list_by_presentation(presentation_id)

    def diff_revisions(self, left_id: UUID, right_id: UUID) -> SlideDiffResult:
        left = self._require_revision(left_id)
        right = self._require_revision(right_id)
        return diff_snapshots(
            left.snapshot,
            right.snapshot,
            slide_id=left.slide_id or right.slide_id,
            presentation_id=left.presentation_id,
            before_label=self._revision_label(left),
            after_label=self._revision_label(right),
        )

    def diff_revision_to_current(
        self,
        revision_id: UUID,
        current: SlideSpec,
    ) -> SlideDiffResult:
        revision = self._require_revision(revision_id)
        current_snapshot = slide_to_snapshot(current)
        return diff_snapshots(
            revision.snapshot,
            current_snapshot,
            slide_id=current.id,
            presentation_id=current.presentation_id,
            before_label=self._revision_label(revision),
            after_label=snapshot_label(current_snapshot, prefix="当前版本"),
        )

    def diff_with_previous(self, revision_id: UUID) -> SlideDiffResult | None:
        revision = self._require_revision(revision_id)
        if revision.slide_id is None:
            return None
        previous = self._revisions.get_previous_revision(revision.slide_id, revision.revision_number)
        if previous is None:
            return None
        return self.diff_revisions(previous.id, revision.id)

    def _require_revision(self, revision_id: UUID) -> SlideRevision:
        revision = self._revisions.get_by_id(revision_id)
        if revision is None:
            raise SlideRevisionNotFoundError(revision_id)
        return revision

    @staticmethod
    def _revision_label(revision: SlideRevision) -> str:
        title = str(revision.snapshot.get("title", ""))
        source = change_source_label(revision.change_source)
        return f"修订 #{revision.revision_number} · {source} · {title}"
