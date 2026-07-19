"""Persist and compare slide revision history."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.revision_service import RevisionService
from archium.application.slide_diff import (
    change_source_label,
    diff_snapshots,
    slide_to_snapshot,
    snapshot_content_fingerprint,
    snapshot_label,
    snapshot_to_slide,
)
from archium.domain.enums import RevisionEntityType, RevisionSource
from archium.domain.revision import EntityRevision, SlideLineageOption
from archium.domain.slide import SlideSpec
from archium.domain.slide_history import SlideDiffResult, SlideRevision
from archium.exceptions import SlideRevisionNotFoundError, WorkflowError


class SlideHistoryService:
    """Slide-specific facade over the unified revision service."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._revisions = RevisionService(session)

    def record_snapshot(
        self,
        slide: SlideSpec,
        change_source: RevisionSource,
        *,
        note: str | None = None,
    ) -> SlideRevision:
        return self._revisions.record(
            entity_type=RevisionEntityType.SLIDE,
            entity_id=slide.id,
            lineage_id=slide.lineage_id,
            presentation_id=slide.presentation_id,
            change_source=change_source,
            snapshot=slide_to_snapshot(slide),
            note=note,
        )

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
                    RevisionSource.REGENERATION,
                    note=note,
                )
            )
        return archived

    def list_revisions(self, slide_id: UUID) -> list[SlideRevision]:
        slide = self._get_slide(slide_id)
        if slide is None:
            return []
        return self.list_revisions_by_lineage(slide.lineage_id)

    def list_revisions_by_lineage(self, lineage_id: UUID) -> list[SlideRevision]:
        return self._revisions.list_by_lineage(lineage_id)

    def list_presentation_revisions(self, presentation_id: UUID) -> list[SlideRevision]:
        return self._revisions.list_by_presentation(
            presentation_id,
            entity_type=RevisionEntityType.SLIDE,
        )

    def list_lineage_options(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
    ) -> list[SlideLineageOption]:
        revisions = self.list_presentation_revisions(presentation_id)
        current_by_lineage = {slide.lineage_id: slide for slide in slides}
        lineage_meta: dict[UUID, dict[str, object]] = {}

        for slide in slides:
            lineage_meta[slide.lineage_id] = {
                "logical_key": slide.logical_key,
                "title": slide.title,
                "order": slide.order,
                "current_slide_id": slide.id,
                "status": "current",
                "latest_revision_number": 0,
            }

        for revision in revisions:
            lineage_id = revision.lineage_id
            snapshot = revision.snapshot
            logical_key = str(snapshot.get("logical_key") or snapshot.get("chapter_id", "slide"))
            if lineage_id not in lineage_meta:
                lineage_meta[lineage_id] = {
                    "logical_key": logical_key,
                    "title": snapshot.get("title", "历史页面"),
                    "order": snapshot.get("order", "?"),
                    "current_slide_id": None,
                    "status": "historical",
                    "latest_revision_number": revision.revision_number,
                }
            else:
                meta = lineage_meta[lineage_id]
                current_latest = meta.get("latest_revision_number", 0)
                latest_number = current_latest if isinstance(current_latest, int) else 0
                meta["latest_revision_number"] = max(latest_number, revision.revision_number)
                if meta["current_slide_id"] is None:
                    meta["status"] = "historical"
                elif revision.change_source == RevisionSource.REGENERATION:
                    meta["status"] = "replaced"

        options: list[SlideLineageOption] = []
        for lineage_id, meta in lineage_meta.items():
            current_slide = current_by_lineage.get(lineage_id)
            status = meta["status"]
            if current_slide is not None and status == "historical":
                status = "current"
            label_prefix = {
                "current": "当前页面",
                "replaced": "已替换页面",
                "historical": "历史孤立页面",
            }[str(status)]
            options.append(
                SlideLineageOption(
                    lineage_id=lineage_id,
                    logical_key=str(meta["logical_key"]),
                    label=(
                        f"{label_prefix} · p{meta['order']} · {meta['title']} "
                        f"({meta['logical_key']})"
                    ),
                    status=status,  # type: ignore[arg-type]
                    current_slide_id=current_slide.id if current_slide else None,
                    latest_revision_number=(
                        meta["latest_revision_number"]
                        if isinstance(meta["latest_revision_number"], int)
                        else 0
                    ),
                )
            )
        return sorted(options, key=lambda item: (item.status != "current", item.label))

    def diff_revisions(self, left_id: UUID, right_id: UUID) -> SlideDiffResult:
        left = self._require_revision(left_id)
        right = self._require_revision(right_id)
        presentation_id = left.presentation_id or right.presentation_id
        if presentation_id is None:
            raise SlideRevisionNotFoundError(left.id)
        return diff_snapshots(
            left.snapshot,
            right.snapshot,
            slide_id=left.entity_id or right.entity_id,
            presentation_id=presentation_id,
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
        previous = self._revisions.get_previous_revision(
            revision.lineage_id,
            revision.revision_number,
        )
        if previous is None:
            return None
        return self.diff_revisions(previous.id, revision.id)

    def restore_at_revision(self, revision_id: UUID) -> SlideSpec:
        revision = self._require_revision(revision_id)
        if revision.entity_type != RevisionEntityType.SLIDE:
            raise WorkflowError("所选修订不是页面内容版本。")
        slide = self._get_slide(revision.entity_id) if revision.entity_id else None
        if slide is None:
            raise WorkflowError("无法定位要恢复的页面。")
        restored = snapshot_to_slide(revision.snapshot, slide)
        from archium.infrastructure.database.repositories import PresentationRepository

        return PresentationRepository(self._session).save_slide(restored)

    def find_restorable_revision(self, slide: SlideSpec) -> EntityRevision | None:
        """Return the revision snapshot to restore for multi-step content undo."""
        revisions = [
            revision
            for revision in self.list_revisions(slide.id)
            if revision.entity_type == RevisionEntityType.SLIDE
        ]
        if not revisions:
            return None
        current = snapshot_content_fingerprint(slide_to_snapshot(slide))
        for index, revision in enumerate(revisions):
            if snapshot_content_fingerprint(revision.snapshot) == current:
                next_index = index + 1
                return revisions[next_index] if next_index < len(revisions) else None
        return revisions[0]

    def restore_previous(self, slide_id: UUID) -> SlideSpec:
        slide = self._get_slide(slide_id)
        if slide is None:
            raise WorkflowError("页面不存在。")
        revision = self.find_restorable_revision(slide)
        if revision is None:
            raise WorkflowError("没有可撤销的内容修订。")
        restored = snapshot_to_slide(revision.snapshot, slide)
        from archium.infrastructure.database.repositories import PresentationRepository

        return PresentationRepository(self._session).save_slide(restored)

    def _require_revision(self, revision_id: UUID) -> EntityRevision:
        revision = self._revisions.get_revision(revision_id)
        if revision is None:
            raise SlideRevisionNotFoundError(revision_id)
        return revision

    def _get_slide(self, slide_id: UUID) -> SlideSpec | None:
        from archium.infrastructure.database.repositories import PresentationRepository

        return PresentationRepository(self._session).get_slide(slide_id)

    @staticmethod
    def _revision_label(revision: EntityRevision) -> str:
        title = str(revision.snapshot.get("title", ""))
        source = change_source_label(revision.change_source)
        return f"修订 #{revision.revision_number} · {source} · {title}"
