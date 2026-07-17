"""Unit tests for Brief and Storyline revision history."""

from __future__ import annotations

from unittest.mock import MagicMock

from archium.agents.brief_builder import BriefBuilder
from archium.agents.narrative_architect import NarrativeArchitect
from archium.application.artifact_history_service import BriefHistoryService, StorylineHistoryService
from archium.application.artifact_lineage import apply_brief_lineage, apply_storyline_lineage
from archium.application.review_models import BriefUpdate, StorylineUpdate
from archium.application.review_service import PresentationReviewService
from archium.domain.enums import ProjectType, SlideChangeSource
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.llm.presentation_schemas import BriefDraft, StorylineDraft
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
    BriefHistoryService(db_session).record_snapshot(brief, SlideChangeSource.GENERATED)

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
    assert any(item.change_source == SlideChangeSource.MANUAL_EDIT for item in revisions)


def test_brief_builder_archives_and_records(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    BriefHistoryService(db_session).record_snapshot(brief, SlideChangeSource.GENERATED)

    llm = MagicMock()
    llm.generate_structured.return_value = BriefDraft(
        title="重新生成 Brief",
        presentation_type="other",
        audience="管理层",
        purpose="立项汇报",
        duration_minutes=20,
        target_slide_count=12,
        core_message="重新生成的核心信息。",
        decisions_required=[],
        audience_concerns=[],
        tone="professional",
        required_sections=[],
        excluded_topics=[],
        language="zh-CN",
    )

    builder = BriefBuilder(db_session, llm)
    regenerated = builder.generate(brief.project_id, brief.presentation_id, MagicMock())

    revisions = BriefHistoryService(db_session).list_revisions_by_lineage(regenerated.lineage_id)
    assert regenerated.lineage_id == brief.lineage_id
    assert regenerated.version == brief.version + 1
    assert len(revisions) >= 2
    assert any(item.change_source == SlideChangeSource.REGENERATION for item in revisions)
    assert any(item.change_source == SlideChangeSource.GENERATED for item in revisions)


def test_storyline_builder_archives_and_records(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    storyline = _seed_storyline(db_session, brief)
    StorylineHistoryService(db_session).record_snapshot(storyline, SlideChangeSource.GENERATED)

    llm = MagicMock()
    llm.generate_structured.return_value = StorylineDraft(
        thesis="重新生成的论点",
        narrative_pattern="problem_solution",
        chapters=[],
    )

    architect = NarrativeArchitect(db_session, llm)
    regenerated = architect.generate(brief.project_id, brief)

    revisions = StorylineHistoryService(db_session).list_revisions_by_lineage(regenerated.lineage_id)
    assert regenerated.lineage_id == storyline.lineage_id
    assert regenerated.version == storyline.version + 1
    assert len(revisions) >= 2
    assert any(item.change_source == SlideChangeSource.REGENERATION for item in revisions)


def test_storyline_manual_edit_records_history(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    storyline = _seed_storyline(db_session, brief)
    StorylineHistoryService(db_session).record_snapshot(storyline, SlideChangeSource.GENERATED)

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
    assert any(item.change_source == SlideChangeSource.MANUAL_EDIT for item in revisions)
