"""Persist and load Studio human visual reviews via entity_revisions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.revision_service import RevisionService
from archium.domain.enums import RevisionEntityType, RevisionSource
from archium.domain.revision import EntityRevision
from archium.domain.visual.benchmark import HumanVisualReview
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository


class HumanVisualReviewService:
    """Store one review record per slide save in the unified revision table."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._revisions = RevisionService(session)
        self._presentations = PresentationRepository(session)

    def save(
        self,
        *,
        presentation_id: UUID,
        slide_id: UUID,
        review: HumanVisualReview,
    ) -> EntityRevision:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError("页面不存在。")
        if slide.presentation_id != presentation_id:
            raise WorkflowError("页面与汇报不匹配。")
        snapshot = review.model_dump(mode="json")
        snapshot["slide_id"] = str(slide_id)
        return self._revisions.record(
            entity_type=RevisionEntityType.HUMAN_VISUAL_REVIEW,
            entity_id=slide_id,
            lineage_id=slide.lineage_id,
            presentation_id=presentation_id,
            change_source=RevisionSource.MANUAL_EDIT,
            snapshot=snapshot,
            note="studio_human_review",
        )

    def load_for_slide(self, presentation_id: UUID, slide_id: UUID) -> HumanVisualReview | None:
        revisions = self._revisions.list_by_presentation(
            presentation_id,
            entity_type=RevisionEntityType.HUMAN_VISUAL_REVIEW,
        )
        latest: EntityRevision | None = None
        for revision in revisions:
            if revision.entity_id != slide_id:
                continue
            if latest is None or revision.revision_number > latest.revision_number:
                latest = revision
        if latest is None:
            return None
        try:
            return HumanVisualReview.model_validate(latest.snapshot)
        except Exception:
            return None

    def load_for_presentation(self, presentation_id: UUID) -> list[HumanVisualReview]:
        revisions = self._revisions.list_by_presentation(
            presentation_id,
            entity_type=RevisionEntityType.HUMAN_VISUAL_REVIEW,
        )
        latest_by_slide: dict[UUID, EntityRevision] = {}
        for revision in revisions:
            if revision.entity_id is None:
                continue
            current = latest_by_slide.get(revision.entity_id)
            if current is None or revision.revision_number > current.revision_number:
                latest_by_slide[revision.entity_id] = revision
        reviews: list[HumanVisualReview] = []
        for revision in latest_by_slide.values():
            try:
                reviews.append(HumanVisualReview.model_validate(revision.snapshot))
            except Exception:
                continue
        return reviews
