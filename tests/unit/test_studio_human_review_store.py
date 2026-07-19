"""Unit tests for human review JSON + DB persistence."""

from __future__ import annotations

from archium.application.studio_human_review_store import (
    load_slide_review,
    save_slide_review,
)
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.benchmark import HumanVisualReview
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from sqlalchemy.orm import Session


def _seed(db_session: Session) -> tuple[object, SlideSpec]:
    project = ProjectRepository(db_session).create(Project(name="Review store"))
    presentations = PresentationRepository(db_session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Deck")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="Deck",
            audience="甲方",
            purpose="测试",
            core_message="核心信息。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="论点。",
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
            title="页面",
            message="核心结论。",
            slide_type=SlideType.CONTENT,
        )
    )
    db_session.commit()
    return presentation, slide


def test_save_and_load_slide_review(db_session: Session, test_settings) -> None:
    presentation, slide = _seed(db_session)
    review = HumanVisualReview(
        case_id=str(slide.id),
        information_hierarchy=4,
        visual_focus=4,
        reading_order=4,
        image_text_relationship=4,
        whitespace_density=4,
        architectural_expression=4,
        aesthetic_finish=4,
        editability=4,
        accepted=True,
        reviewer_notes="studio test",
    )
    path = save_slide_review(
        db_session,
        presentation.id,
        slide.id,
        review,
        settings=test_settings,
    )
    assert path.is_file()
    loaded = load_slide_review(
        db_session,
        presentation.id,
        slide.id,
        settings=test_settings,
    )
    assert loaded is not None
    assert loaded.reviewer_notes == "studio test"
    assert loaded.accepted is True
