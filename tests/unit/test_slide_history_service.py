"""Unit tests for slide revision history and lineage."""

from __future__ import annotations

from archium.application.review_models import SlideUpdate
from archium.application.review_service import PresentationReviewService
from archium.application.slide_history_service import SlideHistoryService
from archium.application.slide_lineage import apply_slide_lineage
from archium.domain.enums import ProjectType, SlideChangeSource, SlideType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, build_slide_logical_key
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from sqlalchemy.orm import Session


def _seed_slide(db_session: Session) -> SlideSpec:
    project = ProjectRepository(db_session).create(
        Project(name="历史测试", project_type=ProjectType.HEALTHCARE)
    )
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="测试汇报")
    )
    slide = SlideSpec(
        presentation_id=presentation.id,
        chapter_id="ch1",
        order=0,
        title="初始标题",
        message="初始观点。",
        slide_type=SlideType.CONTENT,
    )
    return PresentationRepository(db_session).save_slide(slide)


def test_record_snapshot_increments_revision_number_by_lineage(db_session: Session) -> None:
    slide = _seed_slide(db_session)
    history = SlideHistoryService(db_session)

    first = history.record_snapshot(slide, SlideChangeSource.GENERATED)
    second = history.record_snapshot(slide, SlideChangeSource.MANUAL_EDIT)

    assert first.revision_number == 1
    assert second.revision_number == 2
    assert first.lineage_id == slide.lineage_id
    assert second.lineage_id == slide.lineage_id
    assert first.snapshot["title"] == "初始标题"


def test_manual_edit_records_history(db_session: Session) -> None:
    slide = _seed_slide(db_session)
    SlideHistoryService(db_session).record_snapshot(slide, SlideChangeSource.GENERATED)

    review = PresentationReviewService(db_session)
    updated = review.update_slide(
        slide.id,
        SlideUpdate(
            chapter_id="ch1",
            order=0,
            title="编辑后标题",
            message="编辑后观点。",
            slide_type=SlideType.CONTENT.value,
            key_points=["新要点"],
        ),
    )

    revisions = SlideHistoryService(db_session).list_revisions(updated.id)
    assert len(revisions) == 2
    manual_revision = next(
        revision for revision in revisions if revision.change_source == SlideChangeSource.MANUAL_EDIT
    )
    diff = SlideHistoryService(db_session).diff_revision_to_current(manual_revision.id, updated)
    assert diff.has_changes
    assert any(change.field == "title" for change in diff.changes)


def test_archive_before_regeneration(db_session: Session) -> None:
    slide = _seed_slide(db_session)
    history = SlideHistoryService(db_session)
    history.record_snapshot(slide, SlideChangeSource.GENERATED)

    archived = history.archive_slides_before_regeneration([slide])
    assert len(archived) == 1
    assert archived[0].change_source == SlideChangeSource.REGENERATION

    revisions = history.list_revisions_by_lineage(slide.lineage_id)
    assert len(revisions) == 2


def test_regeneration_preserves_lineage_id(db_session: Session) -> None:
    slide = _seed_slide(db_session)
    old_lineage = slide.lineage_id
    old_key = build_slide_logical_key(slide.chapter_id, slide.order)

    new_slide = SlideSpec(
        presentation_id=slide.presentation_id,
        chapter_id=slide.chapter_id,
        order=slide.order,
        title="重新生成标题",
        message="重新生成观点。",
        slide_type=SlideType.CONTENT,
    )
    apply_slide_lineage([new_slide], [slide])

    assert new_slide.lineage_id == old_lineage
    assert new_slide.logical_key == old_key
    assert new_slide.version == slide.version + 1
    assert new_slide.id != slide.id


def test_list_lineage_options_includes_deleted_slide_history(
    db_session: Session,
) -> None:
    slide = _seed_slide(db_session)
    history = SlideHistoryService(db_session)
    history.record_snapshot(slide, SlideChangeSource.GENERATED)
    history.archive_slides_before_regeneration([slide])

    new_slide = SlideSpec(
        presentation_id=slide.presentation_id,
        chapter_id=slide.chapter_id,
        order=slide.order,
        title="新实体",
        message="新观点。",
        slide_type=SlideType.CONTENT,
    )
    apply_slide_lineage([new_slide], [slide])
    saved = PresentationRepository(db_session).save_slide(new_slide)
    history.record_snapshot(saved, SlideChangeSource.GENERATED)

    options = history.list_lineage_options(slide.presentation_id, [saved])
    assert len(options) == 1
    assert options[0].lineage_id == slide.lineage_id
    assert options[0].current_slide_id == saved.id
    revisions = history.list_revisions_by_lineage(slide.lineage_id)
    assert len(revisions) >= 3
