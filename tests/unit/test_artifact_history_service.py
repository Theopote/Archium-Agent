"""Unit tests for Brief and Storyline revision history."""

from __future__ import annotations

from archium.application.artifact_history_service import (
    BriefHistoryService,
    StorylineHistoryService,
)
from archium.application.artifact_lineage import apply_brief_lineage, apply_storyline_lineage
from archium.application.review_models import BriefUpdate, StorylineUpdate
from archium.application.review_service import PresentationReviewService
from archium.domain.enums import ProjectType, RevisionSource
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from sqlalchemy.orm import Session


def _seed_brief(db_session: Session) -> PresentationBrief:
    project = ProjectRepository(db_session).create(
        Project(name="Brief 历史测试", project_type=ProjectType.HEALTHCARE)
    )
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="测试汇报")
    )
    brief = PresentationBrief(
        project_id=project.id,
        presentation_id=presentation.id,
        title="初始 Brief",
        audience="管理层",
        purpose="立项汇报",
        core_message="项目价值明确。",
    )
    return PresentationRepository(db_session).save_brief(brief)


def _seed_storyline(db_session: Session, brief: PresentationBrief) -> Storyline:
    storyline = Storyline(
        presentation_id=brief.presentation_id,
        thesis="总体论点",
        chapters=[],
    )
    return PresentationRepository(db_session).save_storyline(storyline)


def test_brief_lineage_preserved_on_regeneration(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    replacement = PresentationBrief(
        project_id=brief.project_id,
        presentation_id=brief.presentation_id,
        title="新 Brief",
        audience="管理层",
        purpose="立项汇报",
        core_message="更新后的核心信息。",
        version=1,
    )
    apply_brief_lineage(replacement, brief)

    assert replacement.lineage_id == brief.lineage_id
    assert replacement.version == brief.version + 1


def test_storyline_lineage_preserved_on_regeneration(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    previous = _seed_storyline(db_session, brief)
    replacement = Storyline(
        presentation_id=brief.presentation_id,
        thesis="新论点",
        chapters=[],
        version=1,
    )
    apply_storyline_lineage(replacement, previous)

    assert replacement.lineage_id == previous.lineage_id
    assert replacement.version == previous.version + 1


def test_brief_manual_edit_records_history(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    BriefHistoryService(db_session).record_snapshot(brief, RevisionSource.GENERATED)

    review = PresentationReviewService(db_session)
    review.update_brief(
        brief.id,
        BriefUpdate(
            title="编辑后 Brief",
            audience=brief.audience,
            purpose=brief.purpose,
            core_message=brief.core_message,
            duration_minutes=brief.duration_minutes,
            target_slide_count=brief.target_slide_count,
            tone=brief.tone,
            language=brief.language,
            required_sections=list(brief.required_sections),
            decisions_required=list(brief.decisions_required),
            audience_concerns=list(brief.audience_concerns),
            excluded_topics=list(brief.excluded_topics),
        ),
    )

    revisions = BriefHistoryService(db_session).list_revisions(brief.id)
    assert len(revisions) == 2
    assert any(item.change_source == RevisionSource.MANUAL_EDIT for item in revisions)


def test_brief_archive_before_regeneration(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    history = BriefHistoryService(db_session)
    history.record_snapshot(brief, RevisionSource.GENERATED)

    replacement = PresentationBrief(
        project_id=brief.project_id,
        presentation_id=brief.presentation_id,
        title="重新生成 Brief",
        audience=brief.audience,
        purpose=brief.purpose,
        core_message="重新生成的核心信息。",
    )
    history.archive_before_regeneration(brief)
    apply_brief_lineage(replacement, brief)
    saved = PresentationRepository(db_session).save_brief(replacement)
    history.record_snapshot(saved, RevisionSource.GENERATED)

    revisions = history.list_revisions_by_lineage(saved.lineage_id)
    assert saved.lineage_id == brief.lineage_id
    assert saved.version == brief.version + 1
    assert len(revisions) == 3
    assert any(item.change_source == RevisionSource.REGENERATION for item in revisions)


def test_storyline_archive_before_regeneration(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    storyline = _seed_storyline(db_session, brief)
    history = StorylineHistoryService(db_session)
    history.record_snapshot(storyline, RevisionSource.GENERATED)

    replacement = Storyline(
        presentation_id=brief.presentation_id,
        thesis="重新生成的论点",
        chapters=[],
    )
    history.archive_before_regeneration(storyline)
    apply_storyline_lineage(replacement, storyline)
    saved = PresentationRepository(db_session).save_storyline(replacement)
    history.record_snapshot(saved, RevisionSource.GENERATED)

    revisions = history.list_revisions_by_lineage(saved.lineage_id)
    assert saved.lineage_id == storyline.lineage_id
    assert saved.version == storyline.version + 1
    assert len(revisions) == 3
    assert any(item.change_source == RevisionSource.REGENERATION for item in revisions)


def test_storyline_manual_edit_records_history(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    storyline = _seed_storyline(db_session, brief)
    StorylineHistoryService(db_session).record_snapshot(storyline, RevisionSource.GENERATED)

    review = PresentationReviewService(db_session)
    review.update_storyline(
        storyline.id,
        StorylineUpdate(
            thesis="编辑后论点",
            narrative_pattern=storyline.narrative_pattern,
            chapters=[],
        ),
    )

    revisions = StorylineHistoryService(db_session).list_revisions(storyline.id)
    assert len(revisions) == 2
    assert any(item.change_source == RevisionSource.MANUAL_EDIT for item in revisions)
