"""Unit tests for Presentation Studio slide add/delete helpers."""

from __future__ import annotations

import pytest
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.ui.studio_service import add_studio_slide, delete_studio_slide
from sqlalchemy.orm import Session


@pytest.fixture
def seeded_presentation(db_session: Session) -> tuple[Presentation, SlideSpec]:
    projects = ProjectRepository(db_session)
    presentations = PresentationRepository(db_session)
    project = projects.create(Project(name="Studio 测试"))
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Studio Deck")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="Studio Deck",
            audience="甲方",
            purpose="测试",
            core_message="核心信息。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="测试论点。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    presentation.current_brief_id = brief.id
    presentation.current_storyline_id = storyline.id
    presentations.update_presentation(presentation)
    slide = presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="封面",
            message="封面信息",
            slide_type=SlideType.CONTENT,
        )
    )
    db_session.commit()
    return presentation, slide


def test_add_studio_slide_appends_after_index(db_session: Session, seeded_presentation) -> None:
    presentation, slide = seeded_presentation
    new_slide = add_studio_slide(db_session, presentation.id, after_index=0)
    slides = PresentationRepository(db_session).list_slides(presentation.id)
    assert len(slides) == 2
    assert new_slide.order == slide.order + 1
    assert new_slide.title == "新页面"


def test_reorder_studio_slide_moves_to_end(db_session: Session, seeded_presentation) -> None:
    from archium.ui.studio_service import add_studio_slide, reorder_studio_slide

    presentation, slide = seeded_presentation
    second = add_studio_slide(db_session, presentation.id, after_index=0)
    db_session.commit()
    reorder_studio_slide(
        db_session,
        presentation.id,
        from_index=0,
        to_index=1,
    )
    slides = PresentationRepository(db_session).list_slides(presentation.id)
    assert [item.id for item in slides] == [second.id, slide.id]
    assert slides[0].order == 0
    assert slides[1].order == 1


def test_reorder_studio_slide_noop_same_index(db_session: Session, seeded_presentation) -> None:
    from archium.ui.studio_service import reorder_studio_slide

    presentation, slide = seeded_presentation
    reorder_studio_slide(
        db_session,
        presentation.id,
        from_index=0,
        to_index=0,
    )
    slides = PresentationRepository(db_session).list_slides(presentation.id)
    assert slides[0].id == slide.id


def test_delete_studio_slide_blocks_last_page(db_session: Session, seeded_presentation) -> None:
    _presentation, slide = seeded_presentation
    with pytest.raises(WorkflowError, match="至少保留一页"):
        delete_studio_slide(db_session, slide.id)
